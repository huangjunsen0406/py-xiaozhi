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

_MQTT_PUBLISH_TIMEOUT = 5.0
_CONTROL_RECONNECT_DELAY = 60.0


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
        self._control_connect_lock = asyncio.Lock()
        self._control_reconnect_task: asyncio.Task | None = None

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
        """兼容旧调用：连接 MQTT 控制通道后建立 UDP 音频会话。"""
        return await self.open_audio_channel()

    async def start(self) -> bool:
        """应用启动时只建立 MQTT 控制连接，不发送 hello 或打开 UDP。"""
        if self._is_closing:
            return False
        connected = await self._connect_control_channel()
        if not connected:
            self._schedule_control_reconnect()
        return connected

    async def _connect_control_channel(self) -> bool:
        """连接并订阅 Broker 控制通道，不改变音频会话状态。"""
        if self._is_closing:
            logger.warning("连接正在关闭中，取消新的连接尝试")
            return False

        if self.mqtt_client and self.mqtt_client.is_connected():
            return True

        async with self._control_connect_lock:
            if self.mqtt_client and self.mqtt_client.is_connected():
                return True
            return await self._create_control_connection()

    async def _create_control_connection(self) -> bool:
        """创建一次新的 Paho client 并等待 CONNACK。"""

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
            self._disconnect_mqtt_client()

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

        # Broker 自动重连由应用控制；Paho 只负责单次连接及 I/O 线程。
        self.mqtt_client = mqtt.Client(
            client_id=self.client_id, reconnect_on_failure=False
        )
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
                logger.info("已配置TLS加密连接 (已启用证书验证)")
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

        def settle_connect(success: bool, error: Exception | None = None) -> None:
            """仅完成本次 connect() 创建的 Future 一次.

            Paho 的网络回调在独立线程运行。连接超时、取消或旧客户端的
            迟到回调都可能发生在 Future 完成后，必须忽略以免异常泄漏到
            asyncio 事件循环。
            """
            if connect_future.done():
                logger.debug("忽略已完成 MQTT 连接等待结果")
                return
            if success:
                connect_future.set_result(True)
            else:
                connect_future.set_exception(error or RuntimeError("MQTT连接失败"))

        def on_connect_callback(client, userdata, flags, rc, properties=None):
            if rc == 0:
                logger.info("已连接到MQTT服务器")
                self._last_activity_time = time.time()
                self.loop.call_soon_threadsafe(settle_connect, True)
            else:
                logger.error(f"连接MQTT服务器失败，返回码: {rc}")
                self.loop.call_soon_threadsafe(
                    settle_connect,
                    False,
                    Exception(f"连接MQTT服务器失败，返回码: {rc}"),
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
                # 已被完整清理/替换的旧 client 的迟到回调不能干扰当前连接。
                if client is not self.mqtt_client:
                    return
                if self._is_closing:
                    return
                reason = (
                    "MQTT连接正常断开" if rc == 0 else f"MQTT连接断开: {rc}"
                )
                if rc == 0:
                    logger.info(reason)
                else:
                    logger.warning(reason)
                self._schedule_coro(
                    self._handle_broker_disconnect(reason),
                    name=f"broker_disconnect:rc={rc}",
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
            logger.info("MQTT控制连接已建立")
            return True

        except Exception as e:
            logger.error(f"连接MQTT服务器失败: {e}", exc_info=True)
            # 首次连接失败必须停止 Paho 网络线程，避免迟到回调绕过应用状态机。
            await self._do_cleanup()
            if self._on_network_error:
                await self._on_network_error(f"连接MQTT服务器失败: {e}")
            return False

    async def _open_udp_audio_session(self) -> bool:
        """在已连接的 MQTT 控制通道上协商并打开一个 UDP 音频会话."""
        self.server_hello_event = asyncio.Event()
        self.session_id = ""
        self._udp.reset_session()

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
            self._start_connection_monitor()

            if self._on_audio_channel_opened:
                await self._on_audio_channel_opened()
            if self._on_connection_state_changed:
                self._on_connection_state_changed(True, "连接成功")
            return True
        except Exception as e:
            logger.error(f"创建UDP套接字失败: {e}", exc_info=True)
            self._udp.reset_session()
            if self._on_network_error:
                await self._on_network_error(f"创建UDP连接失败: {e}")
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

                return

            if msg_type == "mcp":
                mcp_payload = data.get("payload")
                if isinstance(mcp_payload, dict):
                    logger.info(
                        "[MQTT MCP] 收到服务端请求: method=%s, id=%s",
                        mcp_payload.get("method"),
                        mcp_payload.get("id"),
                    )
                else:
                    logger.warning("[MQTT MCP] 收到无效 MCP payload")

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
            result = self.mqtt_client.publish(self.publish_topic, message, qos=0)
            if result.rc not in (mqtt.MQTT_ERR_SUCCESS, mqtt.MQTT_ERR_AGAIN):
                logger.error("MQTT消息入队失败: rc=%s", result.rc)
                return False

            # Paho 的网络循环独立于 asyncio；在工作线程等待避免阻塞 MCP
            # 握手期间的事件处理，并限制异常网络状态下的等待时间。
            await asyncio.to_thread(
                result.wait_for_publish, timeout=_MQTT_PUBLISH_TIMEOUT
            )
            if not result.is_published():
                logger.error("MQTT消息发布超时: %.1fs", _MQTT_PUBLISH_TIMEOUT)
                return False
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
        if self.is_audio_channel_opened():
            return True
        if not await self._connect_control_channel():
            self._schedule_control_reconnect()
            return False
        return await self._open_udp_audio_session()

    async def close_audio_channel(self):
        """结束当前 UDP 会话，保留 MQTT 控制连接以便下次复用."""
        self._is_closing = True
        try:
            await self._cancel_monitor_task()
            if (
                self.session_id
                and self.mqtt_client
                and self.mqtt_client.is_connected()
            ):
                goodbye_msg = {"type": "goodbye", "session_id": self.session_id}
                await self.send_text(json.dumps(goodbye_msg))
            await self._close_udp_audio_session()
        except Exception as e:
            logger.error(f"关闭音频通道时出错: {e}", exc_info=True)
        finally:
            self._is_closing = False

    def is_audio_channel_opened(self) -> bool:
        if not self.connected or self._is_closing:
            return False
        if not self.mqtt_client or not self.mqtt_client.is_connected():
            return False
        return self._udp.is_ready()

    async def _handle_goodbye(self):
        """服务端主动结束会话：仅释放 UDP，不回发 goodbye。"""
        try:
            await self._cancel_monitor_task()
            await self._close_udp_audio_session()
        except Exception as e:
            logger.error(f"处理goodbye消息时出错: {e}", exc_info=True)

    async def _close_udp_audio_session(self) -> None:
        """释放 UDP 会话状态，不触碰仍可复用的 MQTT broker 连接."""
        was_open = self.connected or self._udp.is_ready()
        self._udp.reset_session()
        self.connected = False
        self.session_id = ""
        logger.info("UDP音频会话已关闭，保留MQTT控制连接")

        if was_open and self._on_audio_channel_closed:
            await self._on_audio_channel_closed()

    async def _handle_broker_disconnect(self, reason: str) -> None:
        """Broker 断线：关闭 UDP 会话，稍后仅重连 MQTT 控制通道。"""
        if self.mqtt_client is None:
            return

        was_audio_open = self.connected or self._udp.is_ready()
        await self._cancel_monitor_task()
        self._disconnect_mqtt_client()

        if was_audio_open:
            await self._close_udp_audio_session()
        else:
            self._udp.reset_session()
            self.session_id = ""

        if not self._is_closing and self._on_network_error:
            await self._on_network_error(f"连接丢失: {reason}")
        if not self._is_closing:
            self._schedule_control_reconnect()

    def _can_reconnect_control(self) -> bool:
        checker = self._idle_checker
        if checker is None:
            return True
        try:
            return bool(checker())
        except Exception as e:
            logger.debug(f"检查 MQTT 重连空闲状态失败: {e}", exc_info=True)
            return False

    def _schedule_control_reconnect(self) -> None:
        """安排 ESP32 同款固定 60 秒、仅空闲时的 Broker 重连。"""
        task = self._control_reconnect_task
        if task is not None and not task.done():
            return
        self._control_reconnect_task = asyncio.create_task(
            self._control_reconnect_loop(), name="mqtt:control_reconnect"
        )

    async def _control_reconnect_loop(self) -> None:
        current_task = asyncio.current_task()
        try:
            while not self._is_closing:
                await asyncio.sleep(_CONTROL_RECONNECT_DELAY)
                if self._is_closing:
                    return
                if not self._can_reconnect_control():
                    logger.info("MQTT 控制连接重连等待设备空闲")
                    continue
                logger.info("MQTT 控制连接断开，开始固定间隔重连")
                if await self._connect_control_channel():
                    logger.info("MQTT 控制连接重连成功（未打开 UDP 会话）")
                    return
        except asyncio.CancelledError:
            logger.debug("MQTT 控制连接重连任务已取消")
        finally:
            if self._control_reconnect_task is current_task:
                self._control_reconnect_task = None

    async def _cancel_control_reconnect_task(self) -> None:
        task = self._control_reconnect_task
        if task is None or task.done() or task is asyncio.current_task():
            return
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        self._control_reconnect_task = None

    def _disconnect_mqtt_client(self) -> None:
        """停止 Paho 网络线程并丢弃 MQTT 客户端（仅完整清理路径调用）."""
        client = self.mqtt_client
        self.mqtt_client = None
        self._last_activity_time = None
        if not client:
            return
        try:
            client.loop_stop()
            client.disconnect()
        except Exception as e:
            logger.warning(f"断开MQTT客户端连接时出错: {e}", exc_info=True)

    async def _shutdown_control_channel(self):
        """应用退出时关闭可跨会话复用的 MQTT 控制连接."""
        await self._cancel_control_reconnect_task()
        self._disconnect_mqtt_client()

    def _stop_udp_receiver(self):
        """停止 UDP（断开回调等路径）."""
        self._udp.stop()

    def __del__(self):
        task = getattr(self, "_control_reconnect_task", None)
        if task is not None and not task.done():
            task.cancel()
        try:
            self._udp.stop()
        except Exception:
            pass
        self._disconnect_mqtt_client()

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
        self._udp.reset_session()
        self.connected = False
        self.session_id = ""
        self._disconnect_mqtt_client()

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
