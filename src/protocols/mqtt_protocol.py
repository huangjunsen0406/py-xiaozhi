"""MQTT + UDP 音频协议实现.

MQTT 承载控制 JSON；UDP 承载加密音频帧（见 mqtt_udp / mqtt_crypto）。
"""

from __future__ import annotations

import asyncio
import json
import time

import paho.mqtt.client as mqtt

from src.constants.constants import AudioConfig
from src.logging import get_logger
from src.protocols.mqtt_udp import MqttUdpChannel
from src.protocols.protocol import Protocol
from src.utils.config_manager import get_config

logger = get_logger()


def parse_mqtt_endpoint(endpoint: str) -> tuple[str, int]:
    """解析 endpoint：hostname 或 hostname:port；默认端口 8883."""
    if not endpoint:
        raise ValueError("endpoint不能为空")

    if ":" in endpoint:
        host, port_str = endpoint.rsplit(":", 1)
        try:
            port = int(port_str)
            if port < 1 or port > 65535:
                raise ValueError(f"端口号必须在1-65535之间: {port}")
        except ValueError as e:
            raise ValueError(f"无效的端口号: {port_str}") from e
    else:
        host = endpoint
        port = 8883

    return host, port


class MqttProtocol(Protocol):
    def __init__(self, loop):
        super().__init__()
        self.loop = loop
        self.config = get_config()
        self.mqtt_client = None
        self.connected = False
        # 线程侧调度的 Future，避免 fire-and-forget create_task
        self._pending_futures: set = set()

        # MQTT 连接活动监控
        self._last_activity_time = None
        self._keep_alive_interval = 60
        self._connection_timeout = 120

        # MQTT 配置（OTA 注入）
        self.endpoint = None
        self.client_id = None
        self.username = None
        self.password = None
        self.publish_topic = None
        self.subscribe_topic = None

        # UDP 音频通道
        self._udp = MqttUdpChannel(loop)
        self._udp.set_audio_handler(self._on_udp_audio)

        self.server_hello_event = asyncio.Event()

    # ---- 兼容旧属性（诊断 / 测试）----
    @property
    def udp_socket(self):
        return self._udp.socket

    @property
    def udp_running(self) -> bool:
        return self._udp.running

    @property
    def udp_server(self) -> str:
        return self._udp.server

    @property
    def udp_port(self) -> int:
        return self._udp.port

    def _on_udp_audio(self, audio_data: bytes) -> None:
        """在 event loop 线程：把 UDP 帧交给协议 on_incoming_audio."""
        cb = self._on_incoming_audio
        if not cb:
            return
        if asyncio.iscoroutinefunction(cb):
            self.loop.create_task(cb(audio_data))
        else:
            cb(audio_data)

    def _schedule_coro(self, coro, name: str = "mqtt") -> None:
        """从任意线程安全调度协程到 event loop，并记录异常."""
        try:
            running_loop = asyncio.get_running_loop()
        except RuntimeError:
            running_loop = None

        def _track_future(fut) -> None:
            self._pending_futures.add(fut)

            def _done(f) -> None:
                self._pending_futures.discard(f)
                try:
                    exc = f.exception()
                except (asyncio.CancelledError, Exception):
                    return
                if exc:
                    logger.error(f"MQTT 调度任务 {name} 异常: {exc}", exc_info=exc)

            fut.add_done_callback(_done)

        if running_loop is self.loop:
            try:
                task = self.loop.create_task(coro, name=f"mqtt:{name}")
                _track_future(task)
            except Exception as e:
                logger.error(f"MQTT 创建任务失败 {name}: {e}", exc_info=True)
                if asyncio.iscoroutine(coro):
                    coro.close()
            return

        try:
            fut = asyncio.run_coroutine_threadsafe(coro, self.loop)
            _track_future(fut)
        except Exception as e:
            logger.error(f"MQTT 跨线程调度失败 {name}: {e}", exc_info=True)
            if asyncio.iscoroutine(coro):
                coro.close()

    async def connect(self):
        """连接到 MQTT 服务器并建立 UDP 音频通道."""
        if self._is_closing:
            logger.warning("连接正在关闭中，取消新的连接尝试")
            return False

        self.server_hello_event = asyncio.Event()

        try:
            mqtt_config = self.config.get_config("SYSTEM_OPTIONS.NETWORK.MQTT_INFO")
            logger.debug(f"MQTT配置: {mqtt_config}")
            self.endpoint = mqtt_config.get("endpoint")
            self.client_id = mqtt_config.get("client_id")
            self.username = mqtt_config.get("username")
            self.password = mqtt_config.get("password")
            self.publish_topic = mqtt_config.get("publish_topic")
            self.subscribe_topic = mqtt_config.get("subscribe_topic")
            logger.info(f"已从OTA服务器获取MQTT配置: {self.endpoint}")
        except Exception as e:
            logger.warning(f"从OTA服务器获取MQTT配置失败: {e}", exc_info=True)

        if (
            not self.endpoint
            or not self.username
            or not self.password
            or not self.publish_topic
        ):
            logger.error("MQTT配置不完整")
            if self._on_network_error:
                await self._on_network_error("MQTT配置不完整")
            return False

        if self.subscribe_topic == "null":
            self.subscribe_topic = None
            logger.info("订阅主题为null，将不订阅任何主题")

        if self.mqtt_client:
            try:
                self.mqtt_client.loop_stop()
                self.mqtt_client.disconnect()
            except Exception as e:
                logger.warning(f"断开MQTT客户端连接时出错: {e}", exc_info=True)

        try:
            host, port = parse_mqtt_endpoint(self.endpoint)
            use_tls = port == 8883
            logger.info(
                f"解析endpoint: {self.endpoint} -> 主机: {host}, 端口: {port}, "
                f"使用TLS: {use_tls}"
            )
        except ValueError as e:
            logger.error(f"解析endpoint失败: {e}", exc_info=True)
            if self._on_network_error:
                await self._on_network_error(f"解析endpoint失败: {e}")
            return False

        self.mqtt_client = mqtt.Client(client_id=self.client_id)
        self.mqtt_client.username_pw_set(self.username, self.password)

        if use_tls:
            try:
                self.mqtt_client.tls_set(
                    ca_certs=None,
                    certfile=None,
                    keyfile=None,
                    cert_reqs=mqtt.ssl.CERT_REQUIRED,
                    tls_version=mqtt.ssl.PROTOCOL_TLS,
                )
                logger.info("已配置TLS加密连接")
            except Exception as e:
                logger.error(
                    f"TLS配置失败，无法安全连接到MQTT服务器: {e}", exc_info=True
                )
                if self._on_network_error:
                    await self._on_network_error(f"TLS配置失败: {str(e)}")
                return False
        else:
            logger.info("使用非TLS连接")

        connect_future = self.loop.create_future()

        def on_connect_callback(client, userdata, flags, rc, properties=None):
            if rc == 0:
                logger.info("已连接到MQTT服务器")
                self._last_activity_time = time.time()
                self.loop.call_soon_threadsafe(lambda: connect_future.set_result(True))
            else:
                logger.error(f"连接MQTT服务器失败，返回码: {rc}")
                self.loop.call_soon_threadsafe(
                    lambda: connect_future.set_exception(
                        Exception(f"连接MQTT服务器失败，返回码: {rc}")
                    )
                )

        def on_message_callback(client, userdata, msg):
            try:
                self._last_activity_time = time.time()
                payload = msg.payload.decode("utf-8")
                self._handle_mqtt_message(payload)
            except Exception as e:
                logger.error(f"处理MQTT消息时出错: {e}", exc_info=True)

        def on_disconnect_callback(client, userdata, rc):
            try:
                if rc == 0:
                    logger.info("MQTT连接正常断开")
                else:
                    logger.warning(f"MQTT连接异常断开，返回码: {rc}")

                was_connected = self.connected
                self.connected = False

                if self._on_connection_state_changed and was_connected:
                    reason = "正常断开" if rc == 0 else f"异常断开(rc={rc})"
                    self.loop.call_soon_threadsafe(
                        lambda: self._on_connection_state_changed(False, reason)
                    )

                self._udp.stop()

                if (
                    rc != 0
                    and not self._is_closing
                    and self._auto_reconnect_enabled
                    and self._reconnect_attempts < self._max_reconnect_attempts
                ):
                    self._schedule_coro(
                        self._attempt_reconnect(f"MQTT断开(rc={rc})"),
                        name=f"reconnect:rc={rc}",
                    )
                else:
                    if self._on_audio_channel_closed:
                        self._schedule_coro(
                            self._on_audio_channel_closed(),
                            name="audio_channel_closed",
                        )
                    if rc != 0 and self._on_network_error:
                        error_msg = f"MQTT连接断开: {rc}"
                        if (
                            self._auto_reconnect_enabled
                            and self._reconnect_attempts >= self._max_reconnect_attempts
                        ):
                            error_msg += " (重连失败)"
                        self._schedule_coro(
                            self._on_network_error(error_msg),
                            name="network_error",
                        )
            except Exception as e:
                logger.error(f"处理MQTT断开连接失败: {e}", exc_info=True)

        def on_publish_callback(client, userdata, mid):
            self._last_activity_time = time.time()

        def on_subscribe_callback(client, userdata, mid, granted_qos):
            logger.info(f"订阅成功，主题: {self.subscribe_topic}")
            self._last_activity_time = time.time()

        self.mqtt_client.on_connect = on_connect_callback
        self.mqtt_client.on_message = on_message_callback
        self.mqtt_client.on_disconnect = on_disconnect_callback
        self.mqtt_client.on_publish = on_publish_callback
        self.mqtt_client.on_subscribe = on_subscribe_callback

        try:
            logger.info(f"正在连接MQTT服务器: {host}:{port}")
            self.mqtt_client.connect_async(
                host, port, keepalive=self._keep_alive_interval
            )
            self.mqtt_client.loop_start()

            await asyncio.wait_for(connect_future, timeout=10.0)

            if self.subscribe_topic:
                self.mqtt_client.subscribe(self.subscribe_topic, qos=1)

            self._start_connection_monitor()

            hello_message = {
                "type": "hello",
                "version": 3,
                "features": {"mcp": True},
                "transport": "udp",
                "audio_params": {
                    "format": "opus",
                    "sample_rate": AudioConfig.INPUT_SAMPLE_RATE,
                    "channels": AudioConfig.CHANNELS,
                    "frame_duration": AudioConfig.FRAME_DURATION,
                },
            }

            if not await self.send_text(json.dumps(hello_message)):
                logger.error("发送hello消息失败")
                return False

            try:
                await asyncio.wait_for(self.server_hello_event.wait(), timeout=10.0)
            except asyncio.TimeoutError:
                logger.error("等待服务器hello消息超时")
                if self._on_network_error:
                    await self._on_network_error("等待响应超时")
                return False

            try:
                self._udp.start()
                self.connected = True
                self._reconnect_attempts = 0

                if self._on_connection_state_changed:
                    self._on_connection_state_changed(True, "连接成功")

                return True
            except Exception as e:
                logger.error(f"创建UDP套接字失败: {e}", exc_info=True)
                if self._on_network_error:
                    await self._on_network_error(f"创建UDP连接失败: {e}")
                return False

        except Exception as e:
            logger.error(f"连接MQTT服务器失败: {e}", exc_info=True)
            if self._on_network_error:
                await self._on_network_error(f"连接MQTT服务器失败: {e}")
            return False

    def _handle_mqtt_message(self, payload):
        """处理 MQTT JSON 消息（线程回调）."""
        try:
            data = json.loads(payload)
            msg_type = data.get("type")

            if msg_type == "goodbye":
                session_id = data.get("session_id")
                if not session_id or session_id == self.session_id:
                    asyncio.run_coroutine_threadsafe(self._handle_goodbye(), self.loop)
                return

            if msg_type == "hello":
                logger.debug(f"服务链接返回初始化配置: {data}")
                transport = data.get("transport")
                if transport != "udp":
                    logger.error(f"不支持的传输方式: {transport}")
                    return

                self.session_id = data.get("session_id", "")

                udp = data.get("udp")
                if not udp:
                    logger.error("UDP配置缺失")
                    return

                self._udp.configure(
                    server=udp.get("server"),
                    port=udp.get("port"),
                    aes_key=udp.get("key"),
                    aes_nonce=udp.get("nonce"),
                )

                logger.info(
                    f"收到服务器hello响应，UDP服务器: "
                    f"{self._udp.server}:{self._udp.port}"
                )

                self.loop.call_soon_threadsafe(self.server_hello_event.set)

                if self._on_audio_channel_opened:
                    self._schedule_coro(
                        self._on_audio_channel_opened(),
                        name="audio_channel_opened",
                    )
                return

            if self._on_incoming_json:

                def process_json(json_data=data):
                    if asyncio.iscoroutinefunction(self._on_incoming_json):
                        coro = self._on_incoming_json(json_data)
                        if coro is not None:
                            asyncio.run_coroutine_threadsafe(coro, self.loop)
                    else:
                        self._on_incoming_json(json_data)

                self.loop.call_soon_threadsafe(process_json)
        except json.JSONDecodeError:
            logger.error(f"无效的JSON数据: {payload}")
        except Exception as e:
            logger.error(f"处理MQTT消息时出错: {e}", exc_info=True)

    async def send_text(self, message):
        if not self.mqtt_client:
            logger.error("MQTT客户端未初始化")
            return False

        try:
            result = self.mqtt_client.publish(self.publish_topic, message)
            result.wait_for_publish()
            return True
        except Exception as e:
            logger.error(f"发送MQTT消息失败: {e}", exc_info=True)
            if self._on_network_error:
                await self._on_network_error(f"发送MQTT消息失败: {e}")
            return False

    async def send_audio(self, audio_data):
        try:
            return self._udp.send_audio(audio_data)
        except Exception as e:
            logger.error(f"发送音频数据失败: {e}", exc_info=True)
            if self._on_network_error:
                self._schedule_coro(
                    self._on_network_error(f"发送音频数据失败: {e}"),
                    name="send_audio_network_error",
                )
            return False

    async def open_audio_channel(self):
        if not self.connected:
            return await self.connect()
        return True

    async def close_audio_channel(self):
        self._is_closing = True
        try:
            if self.session_id:
                goodbye_msg = {"type": "goodbye", "session_id": self.session_id}
                await self.send_text(json.dumps(goodbye_msg))
            await self._handle_goodbye()
        except Exception as e:
            logger.error(f"关闭音频通道时出错: {e}", exc_info=True)
            if self._on_audio_channel_closed:
                await self._on_audio_channel_closed()
        finally:
            self._is_closing = False

    def is_audio_channel_opened(self) -> bool:
        if not self.connected or self._is_closing:
            return False
        if not self.mqtt_client or not self.mqtt_client.is_connected():
            return False
        return self._udp.is_ready()

    async def _handle_goodbye(self):
        try:
            self._udp.reset_session()
            logger.info("UDP接收线程已停止")

            if self.mqtt_client:
                try:
                    self.mqtt_client.loop_stop()
                    self.mqtt_client.disconnect()
                except Exception as e:
                    logger.error(f"断开MQTT连接失败: {e}", exc_info=True)
                self.mqtt_client = None

            self.connected = False
            self.session_id = None

            if self._on_audio_channel_closed:
                await self._on_audio_channel_closed()
        except Exception as e:
            logger.error(f"处理goodbye消息时出错: {e}", exc_info=True)

    def _stop_udp_receiver(self):
        """停止 UDP（断开回调等路径）."""
        self._udp.stop()

    def __del__(self):
        try:
            self._udp.stop()
        except Exception:
            pass
        if getattr(self, "mqtt_client", None):
            try:
                self.mqtt_client.loop_stop()
                self.mqtt_client.disconnect()
            except Exception as e:
                logger.error(f"断开MQTT连接失败: {e}", exc_info=True)

    # ============ 模板方法实现 ============

    @property
    def _monitor_interval(self) -> float:
        return 30.0

    def _is_connected(self) -> bool:
        if not self.mqtt_client or not self.mqtt_client.is_connected():
            return False
        if self._last_activity_time:
            if time.time() - self._last_activity_time > self._connection_timeout:
                return False
        return True

    async def _do_cleanup(self):
        self._udp.stop()
        if self.mqtt_client:
            try:
                self.mqtt_client.loop_stop()
                self.mqtt_client.disconnect()
            except Exception as e:
                logger.error(f"断开MQTT连接时出错: {e}", exc_info=True)
        self._last_activity_time = None

    def get_connection_info(self) -> dict:
        info = super().get_connection_info()
        info.update(
            {
                "connected": self.connected,
                "mqtt_connected": (
                    self.mqtt_client.is_connected() if self.mqtt_client else False
                ),
                "last_activity_time": self._last_activity_time,
                "keep_alive_interval": self._keep_alive_interval,
                "connection_timeout": self._connection_timeout,
                "mqtt_endpoint": self.endpoint,
                "udp_server": (
                    f"{self._udp.server}:{self._udp.port}" if self._udp.server else None
                ),
                "session_id": self.session_id,
            }
        )
        return info
