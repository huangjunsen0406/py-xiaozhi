import asyncio
import json

from src.constants.constants import AbortReason, ListeningMode
from src.logging import get_logger

logger = get_logger()


class Protocol:
    def __init__(self):
        self.session_id = ""
        # 初始化回调函数为None
        self._on_incoming_json = None
        self._on_incoming_audio = None
        self._on_audio_channel_opened = None
        self._on_audio_channel_closed = None
        self._on_network_error = None
        # 新增连接状态变化回调
        self._on_connection_state_changed = None
        self._on_reconnecting = None

        # 连接状态与自动重连（公共，从子类上移）
        self._is_closing = False
        self._reconnect_attempts = 0
        self._max_reconnect_attempts = 5  # 默认重连5次
        self._auto_reconnect_enabled = True  # 默认启用自动重连
        self._connection_monitor_task = None

    def on_incoming_json(self, callback):
        """
        设置JSON消息接收回调函数.
        """
        self._on_incoming_json = callback

    def on_incoming_audio(self, callback):
        """
        设置音频数据接收回调函数.
        """
        self._on_incoming_audio = callback

    def on_audio_channel_opened(self, callback):
        """
        设置音频通道打开回调函数.
        """
        self._on_audio_channel_opened = callback

    def on_audio_channel_closed(self, callback):
        """
        设置音频通道关闭回调函数.
        """
        self._on_audio_channel_closed = callback

    def on_network_error(self, callback):
        """
        设置网络错误回调函数.
        """
        self._on_network_error = callback

    def on_connection_state_changed(self, callback):
        """设置连接状态变化回调函数.

        Args:
            callback: 回调函数，接收参数 (connected: bool, reason: str)
        """
        self._on_connection_state_changed = callback

    def on_reconnecting(self, callback):
        """设置重连尝试回调函数.

        Args:
            callback: 回调函数，接收参数 (attempt: int, max_attempts: int)
        """
        self._on_reconnecting = callback

    async def send_text(self, message):
        """
        发送文本消息的抽象方法，需要在子类中实现.
        """
        raise NotImplementedError("send_text方法必须由子类实现")

    async def send_audio(self, data: bytes):
        """
        发送音频数据的抽象方法，需要在子类中实现.
        """
        raise NotImplementedError("send_audio方法必须由子类实现")

    def is_audio_channel_opened(self) -> bool:
        """
        检查音频通道是否打开的抽象方法，需要在子类中实现.
        """
        raise NotImplementedError("is_audio_channel_opened方法必须由子类实现")

    async def open_audio_channel(self) -> bool:
        """
        打开音频通道的抽象方法，需要在子类中实现.
        """
        raise NotImplementedError("open_audio_channel方法必须由子类实现")

    async def close_audio_channel(self):
        """
        关闭音频通道的抽象方法，需要在子类中实现.
        """
        raise NotImplementedError("close_audio_channel方法必须由子类实现")

    async def send_abort_speaking(self, reason):
        """
        发送中止语音的消息.
        """
        message = {"session_id": self.session_id, "type": "abort"}
        if reason == AbortReason.WAKE_WORD_DETECTED:
            message["reason"] = "wake_word_detected"
        await self.send_text(json.dumps(message))

    async def send_wake_word_detected(self, wake_word):
        """
        发送检测到唤醒词的消息.
        """
        message = {
            "session_id": self.session_id,
            "type": "listen",
            "state": "detect",
            "text": wake_word,
        }
        await self.send_text(json.dumps(message))

    async def send_start_listening(self, mode):
        """
        发送开始监听的消息.
        """
        mode_map = {
            ListeningMode.REALTIME: "realtime",
            ListeningMode.AUTO_STOP: "auto",
            ListeningMode.MANUAL: "manual",
        }
        message = {
            "session_id": self.session_id,
            "type": "listen",
            "state": "start",
            "mode": mode_map[mode],
        }
        await self.send_text(json.dumps(message))

    async def send_stop_listening(self):
        """
        发送停止监听的消息.
        """
        message = {"session_id": self.session_id, "type": "listen", "state": "stop"}
        await self.send_text(json.dumps(message))

    async def send_iot_descriptors(self, descriptors):
        """
        发送物联网设备描述信息.
        """
        try:
            # 解析描述符数据
            if isinstance(descriptors, str):
                descriptors_data = json.loads(descriptors)
            else:
                descriptors_data = descriptors

            # 检查是否为数组
            if not isinstance(descriptors_data, list):
                logger.error("IoT descriptors should be an array")
                return

            # 为每个描述符发送单独的消息
            for i, descriptor in enumerate(descriptors_data):
                if descriptor is None:
                    logger.error(f"Failed to get IoT descriptor at index {i}")
                    continue

                message = {
                    "session_id": self.session_id,
                    "type": "iot",
                    "update": True,
                    "descriptors": [descriptor],
                }

                try:
                    await self.send_text(json.dumps(message))
                except Exception as e:
                    logger.error(
                        f"Failed to send JSON message for IoT descriptor "
                        f"at index {i}: {e}"
                    )
                    continue

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse IoT descriptors: {e}")
            return

    async def send_iot_states(self, states):
        """
        发送物联网设备状态信息.
        """
        if isinstance(states, str):
            states_data = json.loads(states)
        else:
            states_data = states

        message = {
            "session_id": self.session_id,
            "type": "iot",
            "update": True,
            "states": states_data,
        }
        await self.send_text(json.dumps(message))

    async def send_mcp_message(self, payload):
        """
        发送MCP消息.
        """
        if isinstance(payload, str):
            payload_data = json.loads(payload)
        else:
            payload_data = payload

        message = {
            "session_id": self.session_id,
            "type": "mcp",
            "payload": payload_data,
        }

        await self.send_text(json.dumps(message))

    # ============ 连接状态检查（模板方法，子类实现） ============

    def _is_connected(self) -> bool:
        """检查连接是否存活.

        子类必须实现该方法，返回当前协议连接的健康状态.

        Returns:
            bool: 连接存活返回 True，否则返回 False
        """
        raise NotImplementedError("_is_connected方法必须由子类实现")

    # ============ 协议特定清理（模板方法，子类实现） ============

    async def _do_cleanup(self):
        """清理协议特定资源（不包括公共状态和监控任务）.

        子类实现该方法时应：
        - 关闭协议特定的网络连接（socket / websocket / mqtt client 等）
        - 取消协议特定的后台任务（心跳、消息处理等）
        - 重置协议特定的时间戳/状态

        不要在此方法中：
        - 设置 self.connected = False（基类 _handle_connection_loss 负责）
        - 取消 self._connection_monitor_task（基类 _handle_connection_loss 负责）
        """
        raise NotImplementedError("_do_cleanup方法必须由子类实现")

    # ============ 连接监控（公共，子类可覆盖 _monitor_interval） ============

    @property
    def _monitor_interval(self) -> float:
        """连接监控检查间隔（秒），子类可覆盖."""
        return 5.0

    def _start_connection_monitor(self):
        """启动连接健康监控后台任务."""
        if (
            self._connection_monitor_task is None
            or self._connection_monitor_task.done()
        ):
            self._connection_monitor_task = asyncio.create_task(
                self._connection_monitor()
            )

    async def _connection_monitor(self):
        """连接健康状态监控协程.

        循环检查 self._is_connected() 返回值，
        发现断开则调用 self._handle_connection_loss().
        """
        try:
            while not self._is_closing:
                await asyncio.sleep(self._monitor_interval)

                if not self._is_connected():
                    logger.warning("检测到连接已断开")
                    await self._handle_connection_loss("连接检测失败")
                    break

        except asyncio.CancelledError:
            logger.debug("连接监控任务被取消")
        except Exception as e:
            logger.error(f"连接监控异常: {e}")

    # ============ 自动重连（公共） ============

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

    async def _handle_connection_loss(self, reason: str):
        """处理连接丢失（公共逻辑）.

        流程：
        1. 更新连接状态
        2. 取消连接监控任务
        3. 调用子类 _do_cleanup() 清理协议特定资源
        4. 通知观察者（状态变化、音频通道关闭）
        5. 根据配置决定是否自动重连
        """
        logger.warning(f"连接丢失: {reason}")

        was_connected = self.connected
        self.connected = False

        # 取消连接监控任务
        await self._cancel_monitor_task()

        # 通知连接状态变化
        if self._on_connection_state_changed and was_connected:
            try:
                self._on_connection_state_changed(False, reason)
            except Exception as e:
                logger.error(f"调用连接状态变化回调失败: {e}")

        # 调用子类协议特定清理
        await self._do_cleanup()

        # 通知音频通道关闭
        if self._on_audio_channel_closed:
            try:
                await self._on_audio_channel_closed()
            except Exception as e:
                logger.error(f"调用音频通道关闭回调失败: {e}")

        # 根据配置决定是否尝试自动重连
        if (
            not self._is_closing
            and self._auto_reconnect_enabled
            and self._reconnect_attempts < self._max_reconnect_attempts
        ):
            await self._attempt_reconnect(reason)
        else:
            if self._on_network_error:
                if (
                    self._auto_reconnect_enabled
                    and self._reconnect_attempts >= self._max_reconnect_attempts
                ):
                    await self._on_network_error(f"连接丢失且重连失败: {reason}")
                else:
                    await self._on_network_error(f"连接丢失: {reason}")

    async def _attempt_reconnect(self, original_reason: str):
        """尝试自动重连（公共逻辑）.

        使用指数退避策略，调用子类的 connect() 进行实际连接.
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

        # 指数退避等待，最大30秒
        await asyncio.sleep(min(self._reconnect_attempts * 2, 30))

        try:
            success = await self.connect()
            if success:
                logger.info("自动重连成功")
                if self._on_connection_state_changed:
                    self._on_connection_state_changed(True, "重连成功")
            else:
                logger.warning(
                    f"自动重连失败 ({self._reconnect_attempts}/{self._max_reconnect_attempts})"
                )
                if self._reconnect_attempts >= self._max_reconnect_attempts:
                    if self._on_network_error:
                        await self._on_network_error(
                            f"重连失败，已达到最大重连次数: {original_reason}"
                        )
        except Exception as e:
            logger.error(f"重连过程中出错: {e}")
            if self._reconnect_attempts >= self._max_reconnect_attempts:
                if self._on_network_error:
                    await self._on_network_error(f"重连异常: {str(e)}")

    async def _cancel_monitor_task(self):
        """取消并等待连接监控任务完成."""
        if self._connection_monitor_task and not self._connection_monitor_task.done():
            self._connection_monitor_task.cancel()
            try:
                await self._connection_monitor_task
            except asyncio.CancelledError:
                pass

    def get_connection_info(self) -> dict:
        """获取连接信息（基类实现，子类可扩展）.

        Returns:
            dict: 包含连接状态、重连次数等信息的字典
        """
        return {
            "is_closing": self._is_closing,
            "auto_reconnect_enabled": self._auto_reconnect_enabled,
            "reconnect_attempts": self._reconnect_attempts,
            "max_reconnect_attempts": self._max_reconnect_attempts,
        }
