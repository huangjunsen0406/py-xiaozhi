import asyncio
import json
import ssl
import weakref
from typing import Optional, Set

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
        self.websocket: Optional[websockets.WebSocketServerProtocol] = None
        self.connected = False
        self.hello_received: Optional[asyncio.Event] = None
        self.message_task: Optional[asyncio.Task] = None
        
        # 添加任务管理
        self._tasks: Set[asyncio.Task] = set()
        self._shutdown_event = asyncio.Event()
        
        # WebSocket配置
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
            "Device-Id": device_id,
            "Client-Id": client_id,
        }

    def _create_task(self, coro, name: str) -> asyncio.Task:
        """创建并管理任务"""
        task = asyncio.create_task(coro, name=name)
        self._tasks.add(task)
        
        # 使用弱引用避免循环引用
        weak_tasks = weakref.ref(self._tasks)
        
        def done_callback(t):
            tasks = weak_tasks()
            if tasks is not None:
                tasks.discard(t)
            
            if not t.cancelled() and t.exception():
                msg = f"WebSocket任务 {name} 异常结束: {t.exception()}"
                logger.error(msg, exc_info=True)
        
        task.add_done_callback(done_callback)
        return task

    async def connect(self) -> bool:
        """连接到WebSocket服务器."""
        try:
            # 清理现有连接
            await self._cleanup_connections()
            
            # 在连接时创建Event，确保在正确的事件循环中
            self.hello_received = asyncio.Event()
            self._shutdown_event = asyncio.Event()

            # 判断是否应该使用SSL
            current_ssl_context = None
            if self.WEBSOCKET_URL.startswith("wss://"):
                current_ssl_context = ssl_context

            logger.info(f"正在连接到WebSocket服务器: {self.WEBSOCKET_URL}")

            # 建立WebSocket连接
            try:
                # 优先使用新的API
                self.websocket = await websockets.connect(
                    uri=self.WEBSOCKET_URL,
                    ssl=current_ssl_context,
                    additional_headers=self.HEADERS,
                    ping_interval=30,  # 30秒心跳
                    ping_timeout=10,   # 10秒心跳超时
                    close_timeout=10,  # 10秒关闭超时
                )
            except TypeError:
                # 兼容旧版本API
                self.websocket = await websockets.connect(
                    self.WEBSOCKET_URL,
                    ssl=current_ssl_context,
                    extra_headers=self.HEADERS,
                    ping_interval=30,
                    ping_timeout=10,
                )

            # 启动消息处理任务
            task_name = "WebSocket消息处理"
            self.message_task = self._create_task(self._message_handler(), task_name)

            # 发送客户端hello消息
            hello_message = {
                "type": "hello",
                "version": 1,
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
                logger.info("已连接到WebSocket服务器")
                return True
            except asyncio.TimeoutError:
                logger.error("等待服务器hello响应超时")
                if self.on_network_error:
                    await self.on_network_error("等待响应超时")
                return False

        except Exception as e:
            logger.error(f"WebSocket连接失败: {e}")
            if self.on_network_error:
                await self.on_network_error(f"无法连接服务: {str(e)}")
            return False

    async def _message_handler(self):
        """处理接收到的WebSocket消息."""
        try:
            logger.info("WebSocket消息处理器已启动")
            async for message in self.websocket:
                if self._shutdown_event.is_set():
                    break
                    
                try:
                    if isinstance(message, str):
                        # 处理JSON消息
                        await self._handle_text_message(message)
                    elif isinstance(message, bytes):
                        # 处理二进制音频数据
                        await self._handle_binary_message(message)
                    else:
                        logger.warning(f"收到未知类型的消息: {type(message)}")
                        
                except Exception as e:
                    logger.error(f"处理单个消息时出错: {e}", exc_info=True)
                    continue

        except websockets.ConnectionClosed as e:
            logger.info(f"WebSocket连接已关闭: {e}")
            self.connected = False
            await self._handle_connection_closed()
        except asyncio.CancelledError:
            logger.info("WebSocket消息处理任务已取消")
        except Exception as e:
            logger.error(f"WebSocket消息处理错误: {e}", exc_info=True)
            self.connected = False
            if self.on_network_error:
                await self.on_network_error(f"连接错误: {str(e)}")

    async def _handle_text_message(self, message: str):
        """处理文本消息"""
        try:
            data = json.loads(message)
            msg_type = data.get("type")
            
            if msg_type == "hello":
                # 处理服务器hello消息
                await self._handle_server_hello(data)
            else:
                # 处理其他JSON消息
                if self.on_incoming_json:
                    if asyncio.iscoroutinefunction(self.on_incoming_json):
                        await self.on_incoming_json(data)
                    else:
                        self.on_incoming_json(data)
                        
        except json.JSONDecodeError as e:
            logger.error(f"无效的JSON消息: {message}, 错误: {e}")

    async def _handle_binary_message(self, message: bytes):
        """处理二进制消息"""
        if self.on_incoming_audio:
            if asyncio.iscoroutinefunction(self.on_incoming_audio):
                await self.on_incoming_audio(message)
            else:
                self.on_incoming_audio(message)

    async def _handle_connection_closed(self):
        """处理连接关闭"""
        if self.on_audio_channel_closed:
            await self.on_audio_channel_closed()

    async def send_audio(self, data: bytes) -> bool:
        """发送音频数据."""
        if not self.is_audio_channel_opened():
            logger.warning("WebSocket连接未打开，无法发送音频数据")
            self.connected = False
            return False

        try:
            await self.websocket.send(data)
            return True
        except websockets.ConnectionClosed:
            logger.warning("WebSocket连接已关闭，无法发送音频数据")
            self.connected = False
            return False
        except Exception as e:
            logger.error(f"发送音频数据失败: {e}")
            self.connected = False
            if self.on_network_error:
                await self.on_network_error(f"发送音频数据失败: {str(e)}")
            return False

    async def send_text(self, message: str) -> bool:
        """发送文本消息."""
        if not self.websocket:
            logger.error("WebSocket连接未建立")
            self.connected = False
            return False

        try:
            # 检查连接状态
            if self.websocket.closed:
                logger.warning("WebSocket连接已关闭，无法发送文本消息")
                self.connected = False
                return False
                
            await self.websocket.send(message)
            return True
        except websockets.ConnectionClosed:
            logger.warning("WebSocket连接已关闭，无法发送文本消息")
            self.connected = False
            await self.close_audio_channel()
            if self.on_network_error:
                await self.on_network_error("连接已关闭")
            return False
        except Exception as e:
            logger.error(f"发送文本消息失败: {e}")
            self.connected = False
            await self.close_audio_channel()
            if self.on_network_error:
                await self.on_network_error("发送消息失败")
            return False

    def is_audio_channel_opened(self) -> bool:
        """检查音频通道是否打开."""
        try:
            # 检查WebSocket对象是否存在
            if not self.websocket:
                return False
            
            # 检查连接状态标志
            if not self.connected:
                return False
            
            # 检查WebSocket是否已关闭
            if self.websocket.closed:
                logger.warning("WebSocket连接已关闭")
                self.connected = False
                return False
            
            # 检查关闭事件状态
            if self._shutdown_event.is_set():
                return False
            
            # 检查WebSocket连接状态
            if hasattr(self.websocket, 'state'):
                # 新版本websockets库的状态检查
                from websockets.protocol import State
                if self.websocket.state != State.OPEN:
                    logger.warning(f"WebSocket连接状态异常: {self.websocket.state}")
                    self.connected = False
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"检查WebSocket音频通道状态时出错: {e}")
            self.connected = False
            return False

    async def open_audio_channel(self) -> bool:
        """建立WebSocket连接.

        如果尚未连接,则创建新的WebSocket连接
        Returns:
            bool: 连接是否成功
        """
        if not self.is_audio_channel_opened():
            return await self.connect()
        return True

    async def _handle_server_hello(self, data: dict):
        """处理服务器的hello消息."""
        try:
            # 验证传输方式
            transport = data.get("transport")
            if not transport or transport != "websocket":
                logger.error(f"不支持的传输方式: {transport}")
                return
                
            logger.debug("服务器返回初始化配置: %s", data)

            # 设置hello接收事件
            if self.hello_received:
                self.hello_received.set()

            # 通知音频通道已打开
            if self.on_audio_channel_opened:
                await self.on_audio_channel_opened()

            logger.info("成功处理服务器hello消息")

        except Exception as e:
            logger.error(f"处理服务器hello消息时出错: {e}")
            if self.on_network_error:
                await self.on_network_error(f"处理服务器响应失败: {str(e)}")

    async def close_audio_channel(self):
        """关闭音频通道."""
        logger.info("正在关闭WebSocket音频通道")
        
        # 设置关闭标志
        self._shutdown_event.set()
        
        # 清理连接
        await self._cleanup_connections()
        
        # 通知音频通道已关闭
        if self.on_audio_channel_closed:
            await self.on_audio_channel_closed()

    async def _cleanup_connections(self):
        """清理所有连接和任务"""
        try:
            # 设置关闭标志
            self._shutdown_event.set()
            
            # 取消所有任务
            for task in list(self._tasks):
                if not task.done():
                    task.cancel()
                    
            # 等待任务完成
            if self._tasks:
                await asyncio.gather(*self._tasks, return_exceptions=True)
                self._tasks.clear()
            
            # 重置消息任务引用
            self.message_task = None
            
            # 关闭WebSocket连接
            if self.websocket:
                try:
                    if not self.websocket.closed:
                        await self.websocket.close()
                except Exception as e:
                    logger.warning(f"关闭WebSocket连接时出现异常: {e}")
                finally:
                    self.websocket = None
                    
            # 重置状态
            self.connected = False
            
            logger.info("WebSocket连接清理完成")
            
        except Exception as e:
            logger.error(f"清理WebSocket连接时出错: {e}", exc_info=True)

    async def __aenter__(self):
        """异步上下文管理器入口"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self._cleanup_connections()

    def __del__(self):
        """析构函数"""
        # 如果还有未完成的连接，记录警告
        if self.websocket and not self.websocket.closed:
            logger.warning("WebSocket连接在对象销毁时仍然打开，请确保正确调用close_audio_channel()")
