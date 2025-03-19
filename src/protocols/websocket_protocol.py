import asyncio
import json
import logging
import websockets

from src.constants.constants import AudioConfig
from src.protocols.protocol import Protocol
from src.utils.config_manager import ConfigManager


logger = logging.getLogger("WebsocketProtocol")


class WebsocketProtocol(Protocol):
    def __init__(self):
        super().__init__()
        # 获取配置管理器实例
        self.config = ConfigManager.get_instance()
        self.websocket = None
        self.server_sample_rate = AudioConfig.SAMPLE_RATE
        self.connected = False
        self.hello_received = None  # 初始化时先设为 None
        self.WEBSOCKET_URL = self.config.get_config("NETWORK.WEBSOCKET_URL")
        self.WEBSOCKET_ACCESS_TOKEN = self.config.get_config("NETWORK.WEBSOCKET_ACCESS_TOKEN")
        self.CLIENT_ID = self.config.get_client_id()
        self.DEVICE_ID = self.config.get_device_id()

    async def connect(self) -> bool:
        """连接到WebSocket服务器"""
        try:
            # 在连接时创建 Event，确保在正确的事件循环中
            self.hello_received = asyncio.Event()

            # 配置连接
            headers = {
                "Authorization": f"Bearer {self.WEBSOCKET_ACCESS_TOKEN}",
                "Protocol-Version": "1",
                "Device-Id": self.DEVICE_ID,  # 获取设备MAC地址
                "Client-Id": self.CLIENT_ID
            }

            # 建立WebSocket连接 (兼容不同Python版本的写法)
            try:
                # 新的写法 (在Python 3.11+版本中)
                self.websocket = await websockets.connect(
                    uri=self.WEBSOCKET_URL, 
                    additional_headers=headers
                )
            except TypeError:
                # 旧的写法 (在较早的Python版本中)
                self.websocket = await websockets.connect(
                    self.WEBSOCKET_URL, 
                    extra_headers=headers
                )

            # 启动消息处理循环
            asyncio.create_task(self._message_handler())

            # 发送客户端hello消息
            hello_message = {
                "type": "hello",
                "version": 1,
                "transport": "websocket",
                "audio_params": {
                    "format": "opus",
                    "sample_rate": AudioConfig.SAMPLE_RATE,
                    "channels": AudioConfig.CHANNELS,
                    "frame_duration": AudioConfig.FRAME_DURATION,
                }
            }
            await self.send_text(json.dumps(hello_message))

            # 等待服务器hello响应
            try:
                await asyncio.wait_for(
                    self.hello_received.wait(), 
                    timeout=10.0
                )
                self.connected = True
                logger.info("已连接到WebSocket服务器")
                return True
            except asyncio.TimeoutError:
                logger.error("等待服务器hello响应超时")
                if self.on_network_error:
                    self.on_network_error("等待响应超时")
                return False

        except Exception as e:
            logger.error(f"WebSocket连接失败: {e}")
            if self.on_network_error:
                self.on_network_error(f"无法连接服务: {str(e)}")
            return False

    async def _message_handler(self):
        """处理接收到的WebSocket消息"""
        try:
            async for message in self.websocket:
                if isinstance(message, str):
                    try:
                        data = json.loads(message)
                        msg_type = data.get("type")
                        if msg_type == "hello":
                            # 处理服务器 hello 消息
                            await self._handle_server_hello(data)
                        else:
                            if self.on_incoming_json:
                                self.on_incoming_json(data)
                    except json.JSONDecodeError as e:
                        logger.error(f"无效的JSON消息: {message}, 错误: {e}")
                elif self.on_incoming_audio:  # 使用 elif 更清晰
                    self.on_incoming_audio(message)

        except websockets.ConnectionClosed:
            logger.info("WebSocket连接已关闭")
            self.connected = False
            if self.on_audio_channel_closed:
                # 使用 schedule 确保回调在主线程中执行
                await self.on_audio_channel_closed()
        except Exception as e:
            logger.error(f"消息处理错误: {e}")
            self.connected = False
            if self.on_network_error:
                # 使用 schedule 确保错误处理在主线程中执行
                self.on_network_error(f"连接错误: {str(e)}")

    async def send_audio(self, data: bytes):
        """发送音频数据"""
        if not self.is_audio_channel_opened():  # 使用已有的 is_connected 方法
            return

        try:
            await self.websocket.send(data)
        except Exception as e:
            logger.error(f"发送音频数据失败: {e}")
            if self.on_network_error:
                self.on_network_error(f"发送音频失败: {str(e)}")

    async def send_text(self, message: str):
        """发送文本消息"""
        if self.websocket:
            try:
                await self.websocket.send(message)
            except Exception as e:
                await self.close_audio_channel()
                if self.on_network_error:
                    self.on_network_error(f"发送消息失败: {str(e)}")

    def is_audio_channel_opened(self) -> bool:
        """检查音频通道是否打开"""
        return self.websocket is not None and self.connected

    async def open_audio_channel(self) -> bool:
        """建立 WebSocket 连接
        
        如果尚未连接,则创建新的 WebSocket 连接
        Returns:
            bool: 连接是否成功
        """
        if not self.connected:
            return await self.connect()
        return True

    async def _handle_server_hello(self, data: dict):
        """处理服务器的 hello 消息"""
        try:
            # 验证传输方式
            transport = data.get("transport")
            if not transport or transport != "websocket":
                logger.error(f"不支持的传输方式: {transport}")
                return
            print("服务链接返回初始化配置", data)

            # 获取音频参数
            audio_params = data.get("audio_params")
            if audio_params:
                # 更新全局音频配置
                updated = AudioConfig.update_from_server(audio_params)
                if updated:
                    logger.info(f"根据服务器配置更新音频参数: 采样率={AudioConfig.SAMPLE_RATE}, " 
                               f"声道={AudioConfig.CHANNELS}, 帧时长={AudioConfig.FRAME_DURATION}ms, "
                               f"帧大小={AudioConfig.FRAME_SIZE}")
                    
                    # 重新初始化音频编解码器
                    if self.on_audio_config_changed:
                        await self.on_audio_config_changed(AudioConfig)
                
                # 获取服务器的采样率
                sample_rate = audio_params.get("sample_rate")
                if sample_rate:
                    self.server_sample_rate = sample_rate
                    
            # 设置 hello 接收事件
            self.hello_received.set()

            # 通知音频通道已打开
            if self.on_audio_channel_opened:
                await self.on_audio_channel_opened()

            logger.info("成功处理服务器 hello 消息")

        except Exception as e:
            logger.error(f"处理服务器 hello 消息时出错: {e}")
            if self.on_network_error:
                self.on_network_error(f"处理服务器响应失败: {str(e)}")

    async def close_audio_channel(self):
        """关闭音频通道"""
        if self.websocket:
            try:
                await self.websocket.close()
                self.websocket = None
                self.connected = False
                if self.on_audio_channel_closed:
                    await self.on_audio_channel_closed()
            except Exception as e:
                logger.error(f"关闭WebSocket连接失败: {e}")