import asyncio
import json
import ssl
import time

import websockets

from src.constants.constants import AudioConfig
from src.protocols.protocol import Protocol
from src.utils.config_manager import ConfigManager
from src.utils.logging_config import get_logger

ssl_context = ssl._create_unverified_context()

logger = get_logger(__name__)


class WebsocketProtocol(Protocol):
    def __init__(self):
        super().__init__()
        # 获取配置管理器实例
        self.config = ConfigManager.get_instance()
        self.websocket = None
        self.connected = False
        self.hello_received = None  # 初始化时先设为 None
        # 消息处理任务引用，便于在关闭时取消
        self._message_task = None

        # 连接健康状态监测
        self._last_ping_time = None
        self._last_pong_time = None
        self._ping_interval = 30.0  # 心跳间隔（秒）
        self._ping_timeout = 10.0  # ping超时时间（秒）
        self._heartbeat_task = None
        self._connection_monitor_task = None

        # 连接状态标志
        self._is_closing = False
        self._reconnect_attempts = 0
        self._max_reconnect_attempts = 0  # 默认不重连
        self._auto_reconnect_enabled = False  # 默认关闭自动重连

        self.WEBSOCKET_URL = self.config.get_config(
            "SYSTEM_OPTIONS.NETWORK.WEBSOCKET_URL"
        )
        access_token = self.config.get_config(
            "SYSTEM_OPTIONS.NETWORK.WEBSOCKET_ACCESS_TOKEN"
        )
        device_id = self.config.get_config("SYSTEM_OPTIONS.DEVICE_ID")
        client_id = self.config.get_config("SYSTEM_OPTIONS.CLIENT_ID")

        self.HEADERS = {
            "Authorization": f"Bearer {access_token}",
            "Protocol-Version": "1",
            "Device-Id": device_id,  # 获取设备MAC地址
            "Client-Id": client_id,
        }

    async def connect(self) -> bool:
        """
        连接到WebSocket服务器.
        """
        if self._is_closing:
            logger.warning("连接正在关闭中，取消新的连接尝试")
            return False

        try:
            # 在连接时创建 Event，确保在正确的事件循环中
            self.hello_received = asyncio.Event()

            # 判断是否应该使用 SSL
            current_ssl_context = None
            if self.WEBSOCKET_URL.startswith("wss://"):
                current_ssl_context = ssl_context

            # 建立WebSocket连接 (兼容不同Python版本的写法)
            try:
                # 新的写法 (在Python 3.11+版本中)
                self.websocket = await websockets.connect(
                    uri=self.WEBSOCKET_URL,
                    ssl=current_ssl_context,
                    additional_headers=self.HEADERS,
                    ping_interval=20,  # 使用websockets自己的心跳，20秒间隔
                    ping_timeout=20,  # ping超时20秒
                    close_timeout=10,  # 关闭超时10秒
                    max_size=10 * 1024 * 1024,  # 最大消息10MB
                    compression=None,  # 禁用压缩以提高稳定性
                )
            except TypeError:
                # 旧的写法 (在较早的Python版本中)
                self.websocket = await websockets.connect(
                    self.WEBSOCKET_URL,
                    ssl=current_ssl_context,
                    extra_headers=self.HEADERS,
                    ping_interval=20,  # 使用websockets自己的心跳
                    ping_timeout=20,  # ping超时20秒
                    close_timeout=10,  # 关闭超时10秒
                    max_size=10 * 1024 * 1024,  # 最大消息10MB
                    compression=None,  # 禁用压缩
                )

            # 启动消息处理循环（保存任务引用，关闭时可取消）
            self._message_task = asyncio.create_task(self._message_handler())

            # 注释掉自定义心跳，使用websockets内置的心跳机制
            # self._start_heartbeat()

            # 启动连接监控
            self._start_connection_monitor()

            # 发送客户端hello消息
            hello_message = {
                "type": "hello",
                "version": 1,
                "features": {
                    "mcp": True,
                },
                "transport": "websocket",
                "audio_params": {
                    "format": "opus",
                    "sample_rate": AudioConfig.INPUT_SAMPLE_RATE,
                    "channels": AudioConfig.CHANNELS,
                    "frame_duration": AudioConfig.FRAME_DURATION,
                },
            }
            await self.send_text(json.dumps(hello_message))

            # 等待服务器hello响应
            try:
                await asyncio.wait_for(self.hello_received.wait(), timeout=10.0)
                self.connected = True
                self._reconnect_attempts = 0  # 重置重连计数
                logger.info("已连接到WebSocket服务器")

                # 通知连接状态变化
                if self._on_connection_state_changed:
                    self._on_connection_state_changed(True, "连接成功")

                return True
            except asyncio.TimeoutError:
                logger.error("等待服务器hello响应超时")
                await self._cleanup_connection()
                if self._on_network_error:
                    self._on_network_error("等待响应超时")
                return False

        except Exception as e:
            logger.error(f"WebSocket连接失败: {e}")
            await self._cleanup_connection()
            if self._on_network_error:
                self._on_network_error(f"无法连接服务: {str(e)}")
            return False

    def _start_heartbeat(self):
        """
        启动心跳检测任务.
        """
        if self._heartbeat_task is None or self._heartbeat_task.done():
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

    def _start_connection_monitor(self):
        """
        启动连接监控任务.
        """
        if (
            self._connection_monitor_task is None
            or self._connection_monitor_task.done()
        ):
            self._connection_monitor_task = asyncio.create_task(
                self._connection_monitor()
            )

    async def _heartbeat_loop(self):
        """
        心跳检测循环.
        """
        try:
            while self.websocket and not self._is_closing:
                await asyncio.sleep(self._ping_interval)

                if self.websocket and not self._is_closing:
                    try:
                        self._last_ping_time = time.time()
                        # 发送ping并等待pong响应
                        pong_waiter = await self.websocket.ping()
                        logger.debug("发送心跳ping")

                        # 等待pong响应
                        try:
                            await asyncio.wait_for(
                                pong_waiter, timeout=self._ping_timeout
                            )
                            self._last_pong_time = time.time()
                            logger.debug("收到心跳pong响应")
                        except asyncio.TimeoutError:
                            logger.warning("心跳pong响应超时")
                            await self._handle_connection_loss("心跳pong超时")
                            break

                    except Exception as e:
                        logger.error(f"发送心跳失败: {e}")
                        await self._handle_connection_loss("心跳发送失败")
                        break
        except asyncio.CancelledError:
            logger.debug("心跳任务被取消")
        except Exception as e:
            logger.error(f"心跳循环异常: {e}")

    async def _connection_monitor(self):
        """
        连接健康状态监控.
        """
        try:
            while self.websocket and not self._is_closing:
                await asyncio.sleep(5)  # 每5秒检查一次

                # 检查连接状态
                if self.websocket:
                    if self.websocket.close_code is not None:
                        logger.warning("检测到WebSocket连接已关闭")
                        await self._handle_connection_loss("连接已关闭")
                        break

        except asyncio.CancelledError:
            logger.debug("连接监控任务被取消")
        except Exception as e:
            logger.error(f"连接监控异常: {e}")

    async def _handle_connection_loss(self, reason: str):
        """
        处理连接丢失.
        """
        logger.warning(f"连接丢失: {reason}")

        # 更新连接状态
        was_connected = self.connected
        self.connected = False

        # 通知连接状态变化
        if self._on_connection_state_changed and was_connected:
            try:
                self._on_connection_state_changed(False, reason)
            except Exception as e:
                logger.error(f"调用连接状态变化回调失败: {e}")

        # 清理连接
        await self._cleanup_connection()

        # 通知音频通道关闭
        if self._on_audio_channel_closed:
            try:
                await self._on_audio_channel_closed()
            except Exception as e:
                logger.error(f"调用音频通道关闭回调失败: {e}")

        # 只有在启用自动重连且未手动关闭时才尝试重连
        if (
            not self._is_closing
            and self._auto_reconnect_enabled
            and self._reconnect_attempts < self._max_reconnect_attempts
        ):
            await self._attempt_reconnect(reason)
        else:
            # 通知网络错误
            if self._on_network_error:
                if (
                    self._auto_reconnect_enabled
                    and self._reconnect_attempts >= self._max_reconnect_attempts
                ):
                    self._on_network_error(f"连接丢失且重连失败: {reason}")
                else:
                    self._on_network_error(f"连接丢失: {reason}")

    async def _attempt_reconnect(self, original_reason: str):
        """
        尝试自动重连.
        """
        self._reconnect_attempts += 1

        # 通知开始重连
        if self._on_reconnecting:
            try:
                self._on_reconnecting(
                    self._reconnect_attempts, self._max_reconnect_attempts
                )
            except Exception as e:
                logger.error(f"调用重连回调失败: {e}")

        logger.info(
            f"尝试自动重连 ({self._reconnect_attempts}/{self._max_reconnect_attempts})"
        )

        # 等待一段时间后重连
        await asyncio.sleep(min(self._reconnect_attempts * 2, 30))  # 指数退避，最大30秒

        try:
            success = await self.connect()
            if success:
                logger.info("自动重连成功")
                # 通知连接状态变化
                if self._on_connection_state_changed:
                    self._on_connection_state_changed(True, "重连成功")
            else:
                logger.warning(
                    f"自动重连失败 ({self._reconnect_attempts}/{self._max_reconnect_attempts})"
                )
                # 如果还能重试，不立即报错
                if self._reconnect_attempts >= self._max_reconnect_attempts:
                    if self._on_network_error:
                        self._on_network_error(
                            f"重连失败，已达到最大重连次数: {original_reason}"
                        )
        except Exception as e:
            logger.error(f"重连过程中出错: {e}")
            if self._reconnect_attempts >= self._max_reconnect_attempts:
                if self._on_network_error:
                    self._on_network_error(f"重连异常: {str(e)}")

    def enable_auto_reconnect(self, enabled: bool = True, max_attempts: int = 5):
        """启用或禁用自动重连功能.

        Args:
            enabled: 是否启用自动重连
            max_attempts: 最大重连尝试次数
        """
        self._auto_reconnect_enabled = enabled
        if enabled:
            self._max_reconnect_attempts = max_attempts
            logger.info(f"启用自动重连，最大尝试次数: {max_attempts}")
        else:
            self._max_reconnect_attempts = 0
            logger.info("禁用自动重连")

    def get_connection_info(self) -> dict:
        """获取连接信息.

        Returns:
            dict: 包含连接状态、重连次数等信息的字典
        """
        return {
            "connected": self.connected,
            "websocket_closed": (
                self.websocket.close_code is not None if self.websocket else True
            ),
            "is_closing": self._is_closing,
            "auto_reconnect_enabled": self._auto_reconnect_enabled,
            "reconnect_attempts": self._reconnect_attempts,
            "max_reconnect_attempts": self._max_reconnect_attempts,
            "last_ping_time": self._last_ping_time,
            "last_pong_time": self._last_pong_time,
            "websocket_url": self.WEBSOCKET_URL,
        }

    async def _message_handler(self):
        """
        处理接收到的WebSocket消息.
        """
        try:
            async for message in self.websocket:
                if self._is_closing:
                    break

                try:
                    if isinstance(message, str):
                        try:
                            data = json.loads(message)
                            msg_type = data.get("type")
                            if msg_type == "hello":
                                # 处理服务器 hello 消息
                                await self._handle_server_hello(data)
                            else:
                                if self._on_incoming_json:
                                    self._on_incoming_json(data)
                        except json.JSONDecodeError as e:
                            logger.error(f"无效的JSON消息: {message}, 错误: {e}")
                    elif isinstance(message, bytes):
                        # 二进制消息，可能是音频
                        if self._on_incoming_audio:
                            self._on_incoming_audio(message)
                except Exception as e:
                    # 处理单个消息的错误，但继续处理其他消息
                    logger.error(f"处理消息时出错: {e}", exc_info=True)
                    continue

        except asyncio.CancelledError:
            logger.debug("消息处理任务被取消")
            return
        except websockets.ConnectionClosed as e:
            if not self._is_closing:
                logger.info(f"WebSocket连接已关闭: {e}")
                await self._handle_connection_loss(f"连接关闭: {e.code} {e.reason}")
        except websockets.ConnectionClosedError as e:
            if not self._is_closing:
                logger.info(f"WebSocket连接错误关闭: {e}")
                await self._handle_connection_loss(f"连接错误: {e.code} {e.reason}")
        except websockets.InvalidState as e:
            logger.error(f"WebSocket状态无效: {e}")
            await self._handle_connection_loss("连接状态异常")
        except ConnectionResetError:
            logger.warning("连接被重置")
            await self._handle_connection_loss("连接被重置")
        except OSError as e:
            logger.error(f"网络I/O错误: {e}")
            await self._handle_connection_loss("网络I/O错误")
        except Exception as e:
            logger.error(f"消息处理循环异常: {e}", exc_info=True)
            await self._handle_connection_loss(f"消息处理异常: {str(e)}")

    async def send_audio(self, data: bytes):
        """
        发送音频数据.
        """
        if not self.is_audio_channel_opened():
            return

        try:
            await self.websocket.send(data)
        except websockets.ConnectionClosed as e:
            logger.warning(f"发送音频时连接已关闭: {e}")
            await self._handle_connection_loss(f"发送音频失败: {e.code} {e.reason}")
        except websockets.ConnectionClosedError as e:
            logger.warning(f"发送音频时连接错误: {e}")
            await self._handle_connection_loss(f"发送音频错误: {e.code} {e.reason}")
        except Exception as e:
            logger.error(f"发送音频数据失败: {e}")
            # 不要在这里调用网络错误回调，让连接处理器处理
            await self._handle_connection_loss(f"发送音频异常: {str(e)}")

    async def send_text(self, message: str):
        """
        发送文本消息.
        """
        if not self.websocket or self._is_closing:
            logger.warning("WebSocket未连接或正在关闭，无法发送消息")
            return

        try:
            await self.websocket.send(message)
        except websockets.ConnectionClosed as e:
            logger.warning(f"发送文本时连接已关闭: {e}")
            await self._handle_connection_loss(f"发送文本失败: {e.code} {e.reason}")
        except websockets.ConnectionClosedError as e:
            logger.warning(f"发送文本时连接错误: {e}")
            await self._handle_connection_loss(f"发送文本错误: {e.code} {e.reason}")
        except Exception as e:
            logger.error(f"发送文本消息失败: {e}")
            await self._handle_connection_loss(f"发送文本异常: {str(e)}")

    def is_audio_channel_opened(self) -> bool:
        """检查音频通道是否打开.

        更准确地检查连接状态，包括WebSocket的实际状态
        """
        if not self.websocket or not self.connected or self._is_closing:
            return False

        # 检查WebSocket的实际状态
        try:
            return self.websocket.close_code is None
        except Exception:
            return False

    async def open_audio_channel(self) -> bool:
        """建立 WebSocket 连接.

        如果尚未连接,则创建新的 WebSocket 连接
        Returns:
            bool: 连接是否成功
        """
        if not self.is_audio_channel_opened():
            return await self.connect()
        return True

    async def _handle_server_hello(self, data: dict):
        """
        处理服务器的 hello 消息.
        """
        try:
            # 验证传输方式
            transport = data.get("transport")
            if not transport or transport != "websocket":
                logger.error(f"不支持的传输方式: {transport}")
                return

            # 设置 hello 接收事件
            self.hello_received.set()

            # 通知音频通道已打开
            if self._on_audio_channel_opened:
                await self._on_audio_channel_opened()

            logger.info("成功处理服务器 hello 消息")

        except Exception as e:
            logger.error(f"处理服务器 hello 消息时出错: {e}")
            if self._on_network_error:
                self._on_network_error(f"处理服务器响应失败: {str(e)}")

    async def _cleanup_connection(self):
        """
        清理连接相关资源.
        """
        self.connected = False

        # 取消消息处理任务，防止事件循环退出后仍有挂起等待
        if self._message_task and not self._message_task.done():
            self._message_task.cancel()
            try:
                await self._message_task
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.debug(f"等待消息任务取消时异常: {e}")
        self._message_task = None

        # 取消心跳任务
        if self._heartbeat_task and not self._heartbeat_task.done():
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass

        # 取消连接监控任务
        if self._connection_monitor_task and not self._connection_monitor_task.done():
            self._connection_monitor_task.cancel()
            try:
                await self._connection_monitor_task
            except asyncio.CancelledError:
                pass

        # 关闭WebSocket连接
        if self.websocket and self.websocket.close_code is None:
            try:
                await self.websocket.close()
            except Exception as e:
                logger.error(f"关闭WebSocket连接时出错: {e}")

        self.websocket = None
        self._last_ping_time = None
        self._last_pong_time = None

    async def close_audio_channel(self):
        """
        关闭音频通道.
        """
        self._is_closing = True

        try:
            await self._cleanup_connection()

            if self._on_audio_channel_closed:
                await self._on_audio_channel_closed()

        except Exception as e:
            logger.error(f"关闭音频通道失败: {e}")
        finally:
            self._is_closing = False
