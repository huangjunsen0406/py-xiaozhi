"""MQTT 会话配套的 UDP 加密音频通道.

负责：套接字、收包线程、AES 加解密发包；经 event loop 把帧回调给上层。
"""

from __future__ import annotations

import asyncio
import random
import socket
import threading
import time
from collections import deque
from collections.abc import Callable
from enum import Enum
from typing import Any

from src.logging import get_logger
from src.protocols.mqtt_crypto import (
    PROBE_DATAGRAM_SIZE,
    PROBE_TYPE_PING,
    PROBE_TYPE_PONG,
    aes_ctr_decrypt,
    aes_ctr_encrypt,
    build_audio_nonce,
    decode_probe_credentials,
    encode_probe,
    matches_pending_pong,
)

logger = get_logger()

# Bound ingress before scheduling onto the event loop, dropping oldest frames.
_RX_QUEUE_SIZE = 64


class UdpProbeState(str, Enum):
    """UDP 可达性探测健康状态（独立于 socket 可用性）."""

    CLOSED = "closed"
    VERIFYING = "verifying"
    HEALTHY = "healthy"
    SUSPECT = "suspect"
    FAILED = "failed"
    LEGACY_UNVERIFIED = "legacy_unverified"


class MqttUdpChannel:
    """UDP 音频传输（加密 Opus 帧 + 可选认证 PING/PONG 可达性探测）."""

    def __init__(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop
        self.socket: socket.socket | None = None
        self.thread: threading.Thread | None = None
        self.running = False

        self.server = ""
        self.port = 0
        self.aes_key: str | None = None  # hex
        self.aes_nonce: str | None = None  # hex
        self.local_sequence = 0
        self.remote_sequence = 0
        self._remote_sequence_received = False

        self._on_incoming_audio = None
        self._audio_queue: deque[bytes] = deque(maxlen=_RX_QUEUE_SIZE)
        self._audio_lock = threading.Lock()
        self._audio_wake_pending = False
        self._audio_generation = 0

        # 认证 UDP 探测状态（见 xiaozhi-esp32/docs/mqtt-udp-probe_zh.md）
        self.probe_enabled: bool = False
        self.probe_state: UdpProbeState = UdpProbeState.CLOSED
        self._probe_lock = threading.Lock()
        self._probe_generation: int = 0
        self._probe_key: bytes | None = None
        self._probe_ssrc: bytes | None = None
        self._probe_seq: int = 0
        self._pending_ping: bytes | None = None
        self._pending_started_at: float = 0.0
        self._pending_deadline: float = 0.0
        self._pending_attempts: int = 0
        self._last_healthy_at: float | None = None
        self._probe_task: asyncio.Task | None = None
        self._probe_round_done: asyncio.Event | None = None
        self._probe_retry_offsets: tuple[float, ...] = (1.0, 3.0)
        self._probe_budget_s: float = 5.0
        self._probe_interval_s: float = 15.0
        self._probe_jitter_ratio: float = 0.1

    def configure(
        self,
        server: str,
        port: int,
        aes_key: str,
        aes_nonce: str,
        *,
        probe_enabled: bool = False,
    ) -> None:
        probe_key: bytes | None = None
        probe_ssrc: bytes | None = None
        if probe_enabled:
            probe_key, probe_ssrc = decode_probe_credentials(aes_key, aes_nonce)

        self.server = server
        self.port = port
        self.aes_key = aes_key
        self.aes_nonce = aes_nonce
        self.local_sequence = 0
        self.remote_sequence = 0
        self._remote_sequence_received = False

        with self._probe_lock:
            self._probe_generation += 1
            self.probe_enabled = probe_enabled
            self._probe_key = probe_key
            self._probe_ssrc = probe_ssrc
            self._probe_seq = 0
            self._pending_ping = None
            self._pending_attempts = 0
            self._last_healthy_at = None
            self.probe_state = (
                UdpProbeState.VERIFYING
                if probe_enabled
                else UdpProbeState.LEGACY_UNVERIFIED
            )

    def set_audio_handler(self, handler) -> None:
        self._on_incoming_audio = handler

    def is_ready(self) -> bool:
        return (
            self.socket is not None
            and self.running
            and bool(self.server)
            and self.port > 0
            and self.probe_state != UdpProbeState.FAILED
        )

    def start_probe(
        self, on_failure: Callable[[str], Any] | None = None
    ) -> None:
        """在 socket 就绪后按协商结果启动探测（不阻塞等待 PONG）."""
        with self._probe_lock:
            if not self.probe_enabled:
                self.probe_state = UdpProbeState.LEGACY_UNVERIFIED
                return
            generation = self._probe_generation
            ping = self._install_next_probe_round_locked()
            self._probe_round_done = asyncio.Event()

        # 安装 pending 后首发一次 PING，Open 返回前完成发送
        self._send_probe_datagram(ping)
        self._probe_task = self._loop.create_task(
            self._probe_loop(generation, on_failure), name="mqtt:udp_probe"
        )

    def _install_next_probe_round_locked(self) -> bytes:
        if self._probe_key is None or self._probe_ssrc is None:
            raise ValueError("udp_probe_auth_error")
        if self._probe_seq >= 0xFFFFFFFF:
            raise OverflowError("udp_probe_seq_exhausted")
        self._probe_seq += 1
        now = time.monotonic()
        ping = encode_probe(
            PROBE_TYPE_PING, self._probe_key, self._probe_ssrc, self._probe_seq
        )
        self._pending_ping = ping
        self._pending_started_at = now
        self._pending_deadline = now + self._probe_budget_s
        self._pending_attempts = 1
        if self.probe_state != UdpProbeState.HEALTHY:
            self.probe_state = UdpProbeState.VERIFYING
        return ping

    def _send_probe_datagram(self, datagram: bytes) -> bool:
        sock = self.socket
        if sock is None or not self.running or not self.server or not self.port:
            return False
        try:
            sock.sendto(datagram, (self.server, self.port))
            return True
        except OSError as exc:
            logger.debug("发送 UDP 探测包失败: %s", exc)
            return False

    async def _wait_round_until(
        self, target_monotonic: float, done_event: asyncio.Event
    ) -> bool:
        """等待到达目标单调时间或收到有效 PONG；返回 True 表示本轮已收到有效 PONG."""
        remaining = target_monotonic - time.monotonic()
        if remaining <= 0:
            return done_event.is_set()
        try:
            await asyncio.wait_for(done_event.wait(), timeout=remaining)
            return True
        except asyncio.TimeoutError:
            return done_event.is_set()

    async def _run_probe_round(
        self, generation: int, done_event: asyncio.Event
    ) -> bool:
        with self._probe_lock:
            if generation != self._probe_generation:
                return False
            started_at = self._pending_started_at
            deadline = self._pending_deadline

        for offset in self._probe_retry_offsets:
            if await self._wait_round_until(started_at + offset, done_event):
                return True
            with self._probe_lock:
                if generation != self._probe_generation:
                    return False
                if self._pending_ping is None:
                    return True
                if time.monotonic() >= self._pending_deadline:
                    break
                self.probe_state = UdpProbeState.SUSPECT
                self._pending_attempts += 1
                datagram = self._pending_ping
            self._send_probe_datagram(datagram)

        if await self._wait_round_until(deadline, done_event):
            return True

        with self._probe_lock:
            if generation != self._probe_generation:
                return False
            if self._pending_ping is None:
                return True
            self._pending_ping = None
            self.probe_state = UdpProbeState.FAILED
        return False

    async def _probe_loop(
        self, generation: int, on_failure: Callable[[str], Any] | None
    ) -> None:
        try:
            first_round = True
            while True:
                if not first_round:
                    jitter = random.uniform(
                        0.0, self._probe_interval_s * self._probe_jitter_ratio
                    )
                    await asyncio.sleep(self._probe_interval_s + jitter)
                    with self._probe_lock:
                        if generation != self._probe_generation or not self.running:
                            return
                        try:
                            ping = self._install_next_probe_round_locked()
                        except OverflowError:
                            self.probe_state = UdpProbeState.FAILED
                            reason = "udp_probe_seq_exhausted"
                            break
                        except Exception:
                            self.probe_state = UdpProbeState.FAILED
                            reason = "udp_probe_auth_error"
                            break
                        done_event = asyncio.Event()
                        self._probe_round_done = done_event
                    self._send_probe_datagram(ping)
                else:
                    first_round = False
                    with self._probe_lock:
                        done_event = self._probe_round_done
                    if done_event is None:
                        return

                ok = await self._run_probe_round(generation, done_event)
                if not ok:
                    with self._probe_lock:
                        if generation != self._probe_generation:
                            return
                    reason = "udp_probe_timeout"
                    break

            if on_failure is not None:
                result = on_failure(reason)
                if asyncio.iscoroutine(result):
                    await result
        except asyncio.CancelledError:
            return
        except Exception as exc:
            logger.error("UDP 探测循环异常: %s", exc, exc_info=True)

    def _handle_pong(self, data: bytes) -> None:
        """UDP 接收线程入口：先记录单调时间，再加锁校验轮次、截止时间与 HMAC."""
        received_at = time.monotonic()
        with self._probe_lock:
            if (
                not self.probe_enabled
                or self._pending_ping is None
                or self._probe_key is None
            ):
                return
            if received_at > self._pending_deadline:
                return
            if not matches_pending_pong(data, self._pending_ping, self._probe_key):
                return
            attempts = self._pending_attempts
            elapsed_ms = (received_at - self._pending_started_at) * 1000.0
            self._pending_ping = None
            self.probe_state = UdpProbeState.HEALTHY
            self._last_healthy_at = received_at
            done_event = self._probe_round_done

        if attempts == 1:
            logger.info("UDP RTT: %.3f ms", elapsed_ms)
        else:
            logger.info(
                "UDP RTT: unknown after retransmission (attempts=%d, elapsed=%.3f ms)",
                attempts,
                elapsed_ms,
            )
        if done_event is not None:
            try:
                self._loop.call_soon_threadsafe(done_event.set)
            except RuntimeError:
                pass

    def start(self) -> None:
        """创建套接字并启动接收线程（会先 stop 旧资源）."""
        self.stop()

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # 显式绑定，确保 macOS 网络栈正确路由 UDP
        sock.bind(("0.0.0.0", 0))
        sock.settimeout(0.5)
        self.socket = sock

        self.running = True
        self.thread = threading.Thread(
            target=self._receive_loop, name="mqtt-udp-rx", daemon=True
        )
        self.thread.start()
        logger.info(f"UDP接收线程已启动，监听来自 {self.server}:{self.port} 的数据")

    def _request_stop(self) -> None:
        """立即停用旧会话，取消探测任务并丢弃已排队及迟到的音频帧。"""
        with self._probe_lock:
            self._probe_generation += 1
            self._pending_ping = None
            self._probe_round_done = None
            probe_task = self._probe_task
            self._probe_task = None
        if probe_task is not None and not probe_task.done():
            try:
                self._loop.call_soon_threadsafe(probe_task.cancel)
            except RuntimeError:
                pass
        with self._audio_lock:
            self.running = False
            self._audio_generation += 1
            self._audio_queue.clear()
            self._audio_wake_pending = False

    def stop(self) -> None:
        """同步等待接收线程退出；异步生命周期使用 reset_session_async。"""
        self._request_stop()
        if self.thread and self.thread.is_alive():
            # recvfrom 有 0.5s 超时。必须真正退出后才能复用会话字段，
            # 不能依赖跨线程 close 在所有平台唤醒 recvfrom。
            self.thread.join()
        self.thread = None

        if self.socket:
            try:
                self.socket.close()
            except Exception as e:
                logger.error(f"关闭UDP套接字失败: {e}", exc_info=True)
        self.socket = None

    async def reset_session_async(self) -> None:
        """停用旧帧后在线程中等待退出；取消也要等资源释放完成。"""
        self._request_stop()
        cleanup = asyncio.create_task(asyncio.to_thread(self.reset_session))
        cancelled = False
        while not cleanup.done():
            try:
                await asyncio.shield(cleanup)
            except asyncio.CancelledError:
                cancelled = True
        cleanup.result()
        if cancelled:
            raise asyncio.CancelledError

    def reset_session(self) -> None:
        """goodbye 后清空会话侧字段."""
        self.stop()
        self.server = ""
        self.port = 0
        self.aes_key = None
        self.aes_nonce = None
        self.local_sequence = 0
        self.remote_sequence = 0
        self._remote_sequence_received = False
        with self._probe_lock:
            self.probe_enabled = False
            self._probe_key = None
            self._probe_ssrc = None
            self._probe_seq = 0
            self._pending_ping = None
            self._pending_attempts = 0
            self._last_healthy_at = None
            self.probe_state = UdpProbeState.CLOSED

    def send_audio(self, audio_data: bytes) -> bool:
        if not self.socket or not self.server or not self.port:
            logger.error("UDP通道未初始化")
            return False
        if not self.aes_key or not self.aes_nonce:
            logger.error("UDP 加密参数缺失")
            return False

        self.local_sequence = (self.local_sequence + 1) & 0xFFFFFFFF
        new_nonce = build_audio_nonce(
            self.aes_nonce, len(audio_data), self.local_sequence
        )
        encrypt_encoded_data = aes_ctr_encrypt(
            bytes.fromhex(self.aes_key),
            bytes.fromhex(new_nonce),
            bytes(audio_data),
        )
        packet = bytes.fromhex(new_nonce) + encrypt_encoded_data
        self.socket.sendto(packet, (self.server, self.port))

        if self.local_sequence % 10 == 0:
            logger.info(
                f"已发送音频数据包，序列号: {self.local_sequence}，目标: "
                f"{self.server}:{self.port}"
            )
        return True

    def _handle_packet(self, data: bytes, debug_counter: int) -> None:
        # 先按 type 分流认证 PONG，绕过音频解密与音频序号过滤
        if len(data) == PROBE_DATAGRAM_SIZE and data[0] == PROBE_TYPE_PONG:
            self._handle_pong(data)
            return
        if len(data) < 16:
            logger.error(f"无效的音频数据包大小: {len(data)}")
            return
        # MQTT/UDP audio header: type, flags, uint16 payload length,
        # ssrc, timestamp, uint32 sequence (network byte order).
        # See xiaozhi-esp32/docs/mqtt-udp_zh.md, section 4.2.1.
        if data[0] != 0x01:
            logger.warning(f"无效的音频数据包类型: {data[0]:#04x}")
            return
        payload_len = int.from_bytes(data[2:4], "big")
        if len(data) != 16 + payload_len:
            logger.warning(
                f"音频数据包长度不匹配: 声明 {payload_len}，"
                f"实际 {len(data) - 16}"
            )
            return
        sequence = int.from_bytes(data[12:16], "big")
        if self._remote_sequence_received:
            # Serial-number arithmetic permits uint32 wraparound and
            # gaps, but rejects duplicates, late and ambiguous packets.
            distance = (sequence - self.remote_sequence) & 0xFFFFFFFF
            if not 0 < distance < 0x80000000:
                return
        if not self.aes_key:
            return

        decrypted = aes_ctr_decrypt(
            bytes.fromhex(self.aes_key),
            data[:16],
            data[16:],
        )
        self.remote_sequence = sequence
        self._remote_sequence_received = True

        if debug_counter % 100 == 0:
            logger.debug(
                f"已解密音频数据包 #{debug_counter}, 大小: {len(decrypted)} 字节"
            )
        if self._on_incoming_audio:
            self._dispatch_audio(decrypted)

    def _receive_loop(self) -> None:
        debug_counter = 0
        while self.running and self.socket:
            try:
                data, _addr = self.socket.recvfrom(4096)
                debug_counter += 1
                try:
                    self._handle_packet(data, debug_counter)
                except Exception as e:
                    logger.error(f"处理音频数据包错误: {e}", exc_info=True)
            except TimeoutError:
                pass
            except Exception as e:
                logger.error(f"UDP接收线程错误: {e}", exc_info=True)
                if not self.running:
                    break
                time.sleep(0.1)

        logger.info("UDP接收线程已停止")

    def _dispatch_audio(self, audio_data: bytes) -> None:
        """Audio thread: retain bounded frames and coalesce event-loop wakeups."""
        with self._audio_lock:
            if not self.running or self._on_incoming_audio is None:
                return
            self._audio_queue.append(audio_data)
            if self._audio_wake_pending:
                return
            self._audio_wake_pending = True
            generation = self._audio_generation
        self._schedule_audio_drain(generation)

    def _schedule_audio_drain(self, generation: int) -> None:
        try:
            self._loop.call_soon_threadsafe(self._drain_audio, generation)
        except Exception as e:
            with self._audio_lock:
                if generation == self._audio_generation:
                    self._audio_queue.clear()
                    self._audio_wake_pending = False
            logger.error(f"调度音频回调失败: {e}", exc_info=True)

    def _drain_audio(self, generation: int) -> None:
        """Loop thread: deliver a bounded batch, yielding before further frames."""
        for _ in range(_RX_QUEUE_SIZE):
            with self._audio_lock:
                if generation != self._audio_generation:
                    return
                if not self._audio_queue:
                    self._audio_wake_pending = False
                    return
                data = self._audio_queue.popleft()
            handler = self._on_incoming_audio
            if handler is not None:
                try:
                    handler(data)
                except Exception as e:
                    logger.error(f"分发UDP音频失败: {e}", exc_info=True)
        with self._audio_lock:
            if generation != self._audio_generation:
                return
            if not self._audio_queue:
                self._audio_wake_pending = False
                return
        self._schedule_audio_drain(generation)
