import asyncio
import json
import socket
import threading
import time

import paho.mqtt.client as mqtt
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from src.constants.constants import AudioConfig
from src.logging import get_logger
from src.protocols.protocol import Protocol
from src.utils.config_manager import ConfigManager

# 配置日志
logger = get_logger()


class MqttProtocol(Protocol):
    def __init__(self, loop):
        super().__init__()
        self.loop = loop
        self.config = ConfigManager.get_instance()
        self.mqtt_client = None
        self.udp_socket = None
        self.udp_thread = None
        self.udp_running = False
        self.connected = False

        # MQTT 连接活动监控（MQTT特有）
        self._last_activity_time = None
        self._keep_alive_interval = 60  # MQTT保活间隔（秒）
        self._connection_timeout = 120  # 连接超时检测（秒）

        # MQTT配置
        self.endpoint = None
        self.client_id = None
        self.username = None
        self.password = None
        self.publish_topic = None
        self.subscribe_topic = None

        # UDP配置
        self.udp_server = ""
        self.udp_port = 0
        self.aes_key = None
        self.aes_nonce = None
        self.local_sequence = 0
        self.remote_sequence = 0

        # 事件
        self.server_hello_event = asyncio.Event()

    def _parse_endpoint(self, endpoint: str) -> tuple[str, int]:
        """解析endpoint字符串，提取主机和端口.

        Args:
            endpoint: endpoint字符串，格式可以是:
                     - "hostname" (使用默认端口8883)
                     - "hostname:port" (使用指定端口)

        Returns:
            tuple: (host, port) 主机名和端口号
        """
        if not endpoint:
            raise ValueError("endpoint不能为空")

        # 检查是否包含端口
        if ":" in endpoint:
            host, port_str = endpoint.rsplit(":", 1)
            try:
                port = int(port_str)
                if port < 1 or port > 65535:
                    raise ValueError(f"端口号必须在1-65535之间: {port}")
            except ValueError as e:
                raise ValueError(f"无效的端口号: {port_str}") from e
        else:
            # 没有指定端口，使用默认端口8883
            host = endpoint
            port = 8883

        return host, port

    async def connect(self):
        """
        连接到MQTT服务器.
        """
        if self._is_closing:
            logger.warning("连接正在关闭中，取消新的连接尝试")
            return False

        # 重置hello事件
        self.server_hello_event = asyncio.Event()

        # 首先尝试获取MQTT配置
        try:
            # 尝试从OTA服务器获取MQTT配置
            mqtt_config = self.config.get_config("SYSTEM_OPTIONS.NETWORK.MQTT_INFO")

            logger.debug(f"MQTT配置: {mqtt_config}")

            # 更新MQTT配置
            self.endpoint = mqtt_config.get("endpoint")
            self.client_id = mqtt_config.get("client_id")
            self.username = mqtt_config.get("username")
            self.password = mqtt_config.get("password")
            self.publish_topic = mqtt_config.get("publish_topic")
            self.subscribe_topic = mqtt_config.get("subscribe_topic")

            logger.info(f"已从OTA服务器获取MQTT配置: {self.endpoint}")
        except Exception as e:
            logger.warning(f"从OTA服务器获取MQTT配置失败: {e}")

        # 验证MQTT配置
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

        # subscribe_topic 可以为 "null" 字符串，需要特殊处理
        if self.subscribe_topic == "null":
            self.subscribe_topic = None
            logger.info("订阅主题为null，将不订阅任何主题")

        # 如果已有MQTT客户端，先断开连接
        if self.mqtt_client:
            try:
                self.mqtt_client.loop_stop()
                self.mqtt_client.disconnect()
            except Exception as e:
                logger.warning(f"断开MQTT客户端连接时出错: {e}")

        # 解析endpoint，提取主机和端口
        try:
            host, port = self._parse_endpoint(self.endpoint)
            use_tls = port == 8883  # 只有使用8883端口时才使用TLS

            logger.info(
                f"解析endpoint: {self.endpoint} -> 主机: {host}, 端口: {port}, 使用TLS: {use_tls}"
            )
        except ValueError as e:
            logger.error(f"解析endpoint失败: {e}")
            if self._on_network_error:
                await self._on_network_error(f"解析endpoint失败: {e}")
            return False

        # 创建新的MQTT客户端
        self.mqtt_client = mqtt.Client(client_id=self.client_id)
        self.mqtt_client.username_pw_set(self.username, self.password)

        # 根据端口决定是否配置TLS加密连接
        if use_tls:
            try:
                # ca_certs=None 表示使用系统默认CA证书进行验证
                self.mqtt_client.tls_set(
                    ca_certs=None,
                    certfile=None,
                    keyfile=None,
                    cert_reqs=mqtt.ssl.CERT_REQUIRED,
                    tls_version=mqtt.ssl.PROTOCOL_TLS,
                )
                logger.info("已配置TLS加密连接")
            except Exception as e:
                logger.error(f"TLS配置失败，无法安全连接到MQTT服务器: {e}")
                if self._on_network_error:
                    await self._on_network_error(f"TLS配置失败: {str(e)}")
                return False
        else:
            logger.info("使用非TLS连接")

        # 创建连接Future
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
                self._last_activity_time = time.time()  # 更新活动时间
                payload = msg.payload.decode("utf-8")
                self._handle_mqtt_message(payload)
            except Exception as e:
                logger.error(f"处理MQTT消息时出错: {e}")

        def on_disconnect_callback(client, userdata, rc):
            """MQTT断开连接回调.

            Args:
                client: MQTT客户端实例
                userdata: 用户数据
                rc: 返回码 (0=正常断开, >0=异常断开)
            """
            try:
                if rc == 0:
                    logger.info("MQTT连接正常断开")
                else:
                    logger.warning(f"MQTT连接异常断开，返回码: {rc}")

                was_connected = self.connected
                self.connected = False

                # 通知连接状态变化
                if self._on_connection_state_changed and was_connected:
                    reason = "正常断开" if rc == 0 else f"异常断开(rc={rc})"
                    self.loop.call_soon_threadsafe(
                        lambda: self._on_connection_state_changed(False, reason)
                    )

                # 停止UDP接收线程
                self._stop_udp_receiver()

                # 只有在异常断开且启用自动重连时才尝试重连
                if (
                    rc != 0
                    and not self._is_closing
                    and self._auto_reconnect_enabled
                    and self._reconnect_attempts < self._max_reconnect_attempts
                ):
                    # 在事件循环中安排重连
                    self.loop.call_soon_threadsafe(
                        lambda: asyncio.create_task(
                            self._attempt_reconnect(f"MQTT断开(rc={rc})")
                        )
                    )
                else:
                    # 通知音频通道关闭
                    if self._on_audio_channel_closed:
                        asyncio.run_coroutine_threadsafe(
                            self._on_audio_channel_closed(), self.loop
                        )

                    # 通知网络错误
                    if rc != 0 and self._on_network_error:
                        error_msg = f"MQTT连接断开: {rc}"
                        if (
                            self._auto_reconnect_enabled
                            and self._reconnect_attempts >= self._max_reconnect_attempts
                        ):
                            error_msg += " (重连失败)"
                        self.loop.call_soon_threadsafe(
                            lambda: asyncio.create_task(
                                self._on_network_error(error_msg)
                            )
                        )

            except Exception as e:
                logger.error(f"处理MQTT断开连接失败: {e}")

        def on_publish_callback(client, userdata, mid):
            """
            MQTT消息发布回调.
            """
            self._last_activity_time = time.time()  # 更新活动时间

        def on_subscribe_callback(client, userdata, mid, granted_qos):
            """
            MQTT订阅回调.
            """
            logger.info(f"订阅成功，主题: {self.subscribe_topic}")
            self._last_activity_time = time.time()  # 更新活动时间

        # 设置回调
        self.mqtt_client.on_connect = on_connect_callback
        self.mqtt_client.on_message = on_message_callback
        self.mqtt_client.on_disconnect = on_disconnect_callback
        self.mqtt_client.on_publish = on_publish_callback
        self.mqtt_client.on_subscribe = on_subscribe_callback

        try:
            # 连接MQTT服务器，配置保活间隔
            logger.info(f"正在连接MQTT服务器: {host}:{port}")
            self.mqtt_client.connect_async(
                host, port, keepalive=self._keep_alive_interval
            )
            self.mqtt_client.loop_start()

            # 等待连接完成
            await asyncio.wait_for(connect_future, timeout=10.0)

            # 订阅主题
            if self.subscribe_topic:
                self.mqtt_client.subscribe(self.subscribe_topic, qos=1)

            # 启动连接监控
            self._start_connection_monitor()

            # 发送hello消息
            hello_message = {
                "type": "hello",
                "version": 3,
                "features": {
                    "mcp": True,
                },
                "transport": "udp",
                "audio_params": {
                    "format": "opus",
                    "sample_rate": AudioConfig.INPUT_SAMPLE_RATE,
                    "channels": AudioConfig.CHANNELS,
                    "frame_duration": AudioConfig.FRAME_DURATION,
                },
            }

            # 发送消息并等待响应
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

            # 创建UDP套接字
            try:
                if self.udp_socket:
                    self.udp_socket.close()

                self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                self.udp_socket.bind(('0.0.0.0', 0))  # 显式绑定端口，确保macOS网络栈正确路由UDP数据包
                self.udp_socket.settimeout(0.5)

                # 启动UDP接收线程
                if self.udp_thread and self.udp_thread.is_alive():
                    self.udp_running = False
                    self.udp_thread.join(1.0)

                self.udp_running = True
                self.udp_thread = threading.Thread(target=self._udp_receive_thread)
                self.udp_thread.daemon = True
                self.udp_thread.start()

                self.connected = True
                self._reconnect_attempts = 0  # 重置重连计数

                # 通知连接状态变化
                if self._on_connection_state_changed:
                    self._on_connection_state_changed(True, "连接成功")

                return True
            except Exception as e:
                logger.error(f"创建UDP套接字失败: {e}")
                if self._on_network_error:
                    await self._on_network_error(f"创建UDP连接失败: {e}")
                return False

        except Exception as e:
            logger.error(f"连接MQTT服务器失败: {e}")
            if self._on_network_error:
                await self._on_network_error(f"连接MQTT服务器失败: {e}")
            return False

    def _handle_mqtt_message(self, payload):
        """
        处理MQTT消息.
        """
        try:
            data = json.loads(payload)
            msg_type = data.get("type")

            if msg_type == "goodbye":
                # 处理goodbye消息
                session_id = data.get("session_id")
                if not session_id or session_id == self.session_id:
                    # 在主事件循环中执行清理
                    asyncio.run_coroutine_threadsafe(self._handle_goodbye(), self.loop)
                return

            elif msg_type == "hello":
                logger.debug(f"服务链接返回初始化配置: {data}")
                # 处理服务器hello响应
                transport = data.get("transport")
                if transport != "udp":
                    logger.error(f"不支持的传输方式: {transport}")
                    return

                # 获取会话ID
                self.session_id = data.get("session_id", "")

                # 获取UDP配置
                udp = data.get("udp")
                if not udp:
                    logger.error("UDP配置缺失")
                    return

                self.udp_server = udp.get("server")
                self.udp_port = udp.get("port")
                self.aes_key = udp.get("key")
                self.aes_nonce = udp.get("nonce")

                # 重置序列号
                self.local_sequence = 0
                self.remote_sequence = 0

                logger.info(
                    f"收到服务器hello响应，UDP服务器: {self.udp_server}:{self.udp_port}"
                )

                # 设置hello事件
                self.loop.call_soon_threadsafe(self.server_hello_event.set)

                # 触发音频通道打开回调
                if self._on_audio_channel_opened:
                    self.loop.call_soon_threadsafe(
                        lambda: asyncio.create_task(self._on_audio_channel_opened())
                    )

            else:
                # 处理其他JSON消息
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
            logger.error(f"处理MQTT消息时出错: {e}")

    def _udp_receive_thread(self):
        """UDP接收线程.

        参考 audio_player.py 的实现方式
        """
        logger.info(
            f"UDP接收线程已启动，监听来自 {self.udp_server}:{self.udp_port} 的数据"
        )

        self.udp_running = True
        debug_counter = 0

        while self.udp_running:
            try:
                data, addr = self.udp_socket.recvfrom(4096)
                debug_counter += 1

                try:
                    # 验证数据包
                    if len(data) < 16:  # 至少需要16字节的nonce
                        logger.error(f"无效的音频数据包大小: {len(data)}")
                        continue

                    # 分离nonce和加密数据
                    received_nonce = data[:16]
                    encrypted_audio = data[16:]

                    # 使用AES-CTR解密
                    decrypted = self.aes_ctr_decrypt(
                        bytes.fromhex(self.aes_key), received_nonce, encrypted_audio
                    )

                    # 调试信息
                    if debug_counter % 100 == 0:
                        logger.debug(
                            f"已解密音频数据包 #{debug_counter}, 大小: {len(decrypted)} 字节"
                        )

                    # 处理解密后的音频数据
                    if self._on_incoming_audio:

                        def process_audio(audio_data=decrypted):
                            if asyncio.iscoroutinefunction(self._on_incoming_audio):
                                coro = self._on_incoming_audio(audio_data)
                                if coro is not None:
                                    # 在事件循环中安全地创建任务
                                    asyncio.run_coroutine_threadsafe(coro, self.loop)
                            else:
                                self._on_incoming_audio(audio_data)

                        self.loop.call_soon_threadsafe(process_audio)

                except Exception as e:
                    logger.error(f"处理音频数据包错误: {e}")
                    continue

            except TimeoutError:
                # 超时是正常的，继续循环
                pass
            except Exception as e:
                logger.error(f"UDP接收线程错误: {e}")
                if not self.udp_running:
                    break
                time.sleep(0.1)  # 避免在错误情况下过度消耗CPU

        logger.info("UDP接收线程已停止")

    async def send_text(self, message):
        """
        发送文本消息.
        """
        if not self.mqtt_client:
            logger.error("MQTT客户端未初始化")
            return False

        try:
            result = self.mqtt_client.publish(self.publish_topic, message)
            result.wait_for_publish()
            return True
        except Exception as e:
            logger.error(f"发送MQTT消息失败: {e}")
            if self._on_network_error:
                await self._on_network_error(f"发送MQTT消息失败: {e}")
            return False

    async def send_audio(self, audio_data):
        """发送音频数据.

        参考 audio_sender.py 的实现方式
        """
        if not self.udp_socket or not self.udp_server or not self.udp_port:
            logger.error("UDP通道未初始化")
            return False

        try:
            # 生成新的nonce (类似于 audio_sender.py 中的实现)
            # 格式: 0x01 (1字节) + 0x00 (3字节) + 长度 (2字节) + 原始nonce (8字节) + 序列号 (8字节)
            self.local_sequence = (self.local_sequence + 1) & 0xFFFFFFFF
            new_nonce = (
                self.aes_nonce[:4]  # 固定前缀
                + format(len(audio_data), "04x")  # 数据长度
                + self.aes_nonce[8:24]  # 原始nonce
                + format(self.local_sequence, "08x")  # 序列号
            )

            encrypt_encoded_data = self.aes_ctr_encrypt(
                bytes.fromhex(self.aes_key), bytes.fromhex(new_nonce), bytes(audio_data)
            )

            # 拼接nonce和密文
            packet = bytes.fromhex(new_nonce) + encrypt_encoded_data

            # 发送数据包
            self.udp_socket.sendto(packet, (self.udp_server, self.udp_port))

            # 每发送10个包打印一次日志
            if self.local_sequence % 10 == 0:
                logger.info(
                    f"已发送音频数据包，序列号: {self.local_sequence}，目标: "
                    f"{self.udp_server}:{self.udp_port}"
                )
            return True
        except Exception as e:
            logger.error(f"发送音频数据失败: {e}")
            if self._on_network_error:
                asyncio.create_task(self._on_network_error(f"发送音频数据失败: {e}"))
            return False

    async def open_audio_channel(self):
        """
        打开音频通道.
        """
        if not self.connected:
            return await self.connect()
        return True

    async def close_audio_channel(self):
        """
        关闭音频通道.
        """
        self._is_closing = True

        try:
            # 如果有会话ID，发送goodbye消息
            if self.session_id:
                goodbye_msg = {"type": "goodbye", "session_id": self.session_id}
                await self.send_text(json.dumps(goodbye_msg))

            # 处理goodbye
            await self._handle_goodbye()

        except Exception as e:
            logger.error(f"关闭音频通道时出错: {e}")
            # 确保即使出错也调用回调
            if self._on_audio_channel_closed:
                await self._on_audio_channel_closed()
        finally:
            self._is_closing = False

    def is_audio_channel_opened(self) -> bool:
        """检查音频通道是否已打开.

        更准确地检查连接状态，包括MQTT和UDP的实际状态
        """
        if not self.connected or self._is_closing:
            return False

        # 检查MQTT连接状态
        if not self.mqtt_client or not self.mqtt_client.is_connected():
            return False

        # 检查UDP连接状态
        return self.udp_socket is not None and self.udp_running

    def aes_ctr_encrypt(self, key, nonce, plaintext):
        """AES-CTR模式加密函数
        Args:
            key: bytes格式的加密密钥
            nonce: bytes格式的初始向量
            plaintext: 待加密的原始数据
        Returns:
            bytes格式的加密数据
        """
        cipher = Cipher(
            algorithms.AES(key), modes.CTR(nonce), backend=default_backend()
        )
        encryptor = cipher.encryptor()
        return encryptor.update(plaintext) + encryptor.finalize()

    def aes_ctr_decrypt(self, key, nonce, ciphertext):
        """AES-CTR模式解密函数
        Args:
            key: bytes格式的解密密钥
            nonce: bytes格式的初始向量（需要与加密时使用的相同）
            ciphertext: bytes格式的加密数据
        Returns:
            bytes格式的解密后的原始数据
        """
        cipher = Cipher(
            algorithms.AES(key), modes.CTR(nonce), backend=default_backend()
        )
        decryptor = cipher.decryptor()
        plaintext = decryptor.update(ciphertext) + decryptor.finalize()
        return plaintext

    async def _handle_goodbye(self):
        """
        处理goodbye消息.
        """
        try:
            # 停止UDP接收线程
            if self.udp_thread and self.udp_thread.is_alive():
                self.udp_running = False
                self.udp_thread.join(1.0)
                self.udp_thread = None
            logger.info("UDP接收线程已停止")

            # 关闭UDP套接字
            if self.udp_socket:
                try:
                    self.udp_socket.close()
                except Exception as e:
                    logger.error(f"关闭UDP套接字失败: {e}")
                self.udp_socket = None

            # 停止MQTT客户端
            if self.mqtt_client:
                try:
                    self.mqtt_client.loop_stop()
                    self.mqtt_client.disconnect()
                except Exception as e:
                    logger.error(f"断开MQTT连接失败: {e}")
                self.mqtt_client = None

            # 重置所有状态
            self.connected = False
            self.session_id = None
            self.local_sequence = 0
            self.remote_sequence = 0
            self.udp_server = ""
            self.udp_port = 0
            self.aes_key = None
            self.aes_nonce = None

            # 调用音频通道关闭回调
            if self._on_audio_channel_closed:
                await self._on_audio_channel_closed()

        except Exception as e:
            logger.error(f"处理goodbye消息时出错: {e}")

    def _stop_udp_receiver(self):
        """
        停止UDP接收线程和关闭UDP套接字.
        """
        # 关闭UDP接收线程
        if (
            hasattr(self, "udp_thread")
            and self.udp_thread
            and self.udp_thread.is_alive()
        ):
            self.udp_running = False
            try:
                self.udp_thread.join(1.0)
            except RuntimeError:
                pass  # 处理线程已经终止的情况

        # 关闭UDP套接字
        if hasattr(self, "udp_socket") and self.udp_socket:
            try:
                self.udp_socket.close()
            except Exception as e:
                logger.error(f"关闭UDP套接字失败: {e}")

    def __del__(self):
        """
        析构函数，清理资源.
        """
        # 停止UDP接收相关资源
        self._stop_udp_receiver()

        # 关闭MQTT客户端
        if hasattr(self, "mqtt_client") and self.mqtt_client:
            try:
                self.mqtt_client.loop_stop()
                self.mqtt_client.disconnect()
            except Exception as e:
                logger.error(f"断开MQTT连接失败: {e}")

    # ============ 模板方法实现 ============

    @property
    def _monitor_interval(self) -> float:
        """MQTT 连接监控检查间隔（秒）."""
        return 30.0

    def _is_connected(self) -> bool:
        """检查 MQTT 连接是否存活.

        同时检查 TCP 连接状态和活动超时.
        """
        if not self.mqtt_client or not self.mqtt_client.is_connected():
            return False
        if self._last_activity_time:
            time_since_activity = time.time() - self._last_activity_time
            if time_since_activity > self._connection_timeout:
                return False
        return True

    async def _do_cleanup(self):
        """MQTT 协议特定资源清理.

        清理 UDP socket、MQTT 客户端 loop 和连接、活动时间戳.
        """
        # 停止UDP接收线程
        self._stop_udp_receiver()

        # 停止MQTT客户端
        if self.mqtt_client:
            try:
                self.mqtt_client.loop_stop()
                self.mqtt_client.disconnect()
            except Exception as e:
                logger.error(f"断开MQTT连接时出错: {e}")

        # 重置时间戳
        self._last_activity_time = None

    def get_connection_info(self) -> dict:
        """获取 MQTT 连接信息.

        Returns:
            dict: 包含连接状态、重连次数等信息的字典
        """
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
                    f"{self.udp_server}:{self.udp_port}" if self.udp_server else None
                ),
                "session_id": self.session_id,
            }
        )
        return info
