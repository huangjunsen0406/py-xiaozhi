import asyncio
import json
import ssl

import websockets

from src.constants.constants import AudioConfig
from src.logging import get_logger
from src.protocols.protocol import Protocol
from src.utils.config_manager import ConfigManager

# 服务器可能使用自签名证书，暂时跳过客户端证书验证
# 以避免生产环境中非正规SSL证书导致连接失败
ssl_context = ssl._create_unverified_context()

logger = get_logger()


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
                    ping_interval=20,
                    ping_timeout=20,
                    close_timeout=10,
                    open_timeout=5,
                    max_size=10 * 1024 * 1024,
                    compression=None,
                    proxy=None,
                )
            except TypeError:
                # 旧的写法 (在较早的Python版本中)
                self.websocket = await websockets.connect(
                    self.WEBSOCKET_URL,
                    ssl=current_ssl_context,
                    extra_headers=self.HEADERS,
                    ping_interval=20,
                    ping_timeout=20,
                    close_timeout=10,
                    open_timeout=5,
                    max_size=10 * 1024 * 1024,
                    compression=None,
                )

            # 启动消息处理循环（保存任务引用，关闭时可取消）
            self._message_task = asyncio.create_task(self._message_handler())

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
                await self._do_cleanup()
                if self._on_network_error:
                    await self._on_network_error("等待响应超时")
                return False

        except Exception as e:
            logger.error(f"WebSocket连接失败: {e}")
            await self._do_cleanup()
            if self._on_network_error:
                await self._on_network_error(f"无法连接服务: {str(e)}")
            return False

    # ============ 模板方法实现 ============

    @property
    def _monitor_interval(self) -> float:
        """WSS 连接监控检查间隔（秒）."""
        return 5.0

    def _is_connected(self) -> bool:
        """检查 WebSocket 连接是否存活."""
        if not self.websocket:
            return False
        return self.websocket.close_code is None

    async def _do_cleanup(self):
        """WebSocket 协议特定资源清理.

        清理消息处理任务、心跳任务、WebSocket 连接和心跳时间戳.
        不负责取消连接监控任务（基类 _handle_connection_loss 负责）.
        """
        # 取消消息处理任务
        if self._message_task and not self._message_task.done():
            self._message_task.cancel()
            try:
                await self._message_task
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.debug(f"等待消息任务取消时异常: {e}")
        self._message_task = None

        # 关闭WebSocket连接
        if self.websocket and self.websocket.close_code is None:
            try:
                await self.websocket.close()
            except Exception as e:
                logger.error(f"关闭WebSocket连接时出错: {e}")

        self.websocket = None

    def get_connection_info(self) -> dict:
        """获取 WSS 连接信息.

        Returns:
            dict: 包含连接状态、重连次数等信息的字典
        """
        info = super().get_connection_info()
        info.update(
            {
                "connected": self.connected,
                "websocket_closed": (
                    self.websocket.close_code is not None if self.websocket else True
                ),
                "websocket_url": self.WEBSOCKET_URL,
            }
        )
        return info

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
                await self._on_network_error(f"处理服务器响应失败: {str(e)}")

    async def close_audio_channel(self):
        """
        关闭音频通道.
        """
        self._is_closing = True

        try:
            self.connected = False

            # 取消连接监控任务（基类管理）
            await self._cancel_monitor_task()

            # 协议特定清理
            await self._do_cleanup()

            if self._on_audio_channel_closed:
                await self._on_audio_channel_closed()

        except Exception as e:
            logger.error(f"关闭音频通道失败: {e}")
        finally:
            self._is_closing = False
