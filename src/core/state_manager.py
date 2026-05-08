"""状态管理器.

集中管理设备状态，通过事件总线广播状态变更。
"""

import asyncio
from typing import TYPE_CHECKING

from src.constants.constants import DeviceState, ListeningMode
from src.core.event_bus import EventBus, Events
from src.logging import get_logger

if TYPE_CHECKING:
    pass

logger = get_logger()


class StateManager:
    """设备状态管理器.

    职责:
    - 管理设备状态 (IDLE, LISTENING, SPEAKING)
    - 管理监听模式 (REALTIME, AUTO_STOP, MANUAL)
    - 管理会话状态 (keep_listening, aec_enabled)
    - 通过事件总线广播状态变更

    用法:
        state = StateManager(event_bus)

        # 设置状态（会自动广播）
        await state.set_device_state(DeviceState.LISTENING)

        # 读取状态
        if state.is_listening():
            ...
    """

    def __init__(self, event_bus: EventBus, aec_enabled: bool = True):
        self._event_bus = event_bus
        self._lock = asyncio.Lock()

        # 设备状态
        self._device_state: DeviceState = DeviceState.IDLE

        # AEC 配置
        self._aec_enabled: bool = aec_enabled

        # 监听模式：根据 AEC 配置决定默认模式
        self._listening_mode: ListeningMode = (
            ListeningMode.REALTIME if aec_enabled else ListeningMode.AUTO_STOP
        )

        # 会话状态
        self._keep_listening: bool = False

        # 中止标志
        self._aborted: bool = False

    # -------------------------
    # 设备状态
    # -------------------------
    @property
    def device_state(self) -> DeviceState:
        """
        获取当前设备状态.
        """
        return self._device_state

    async def set_device_state(self, state: DeviceState) -> None:
        """设置设备状态.

        Args:
            state: 新的设备状态

        如果状态发生变化，会通过事件总线广播。
        """
        async with self._lock:
            if self._device_state == state:
                return

            old_state = self._device_state
            self._device_state = state
            logger.info(f"设备状态变更: {old_state} -> {state}")

            # 重置中止标志
            if state == DeviceState.LISTENING:
                self._aborted = False

        # 在锁外广播，避免死锁
        await self._event_bus.emit(
            Events.DEVICE_STATE_CHANGED,
            {"old_state": old_state, "new_state": state},
        )

    def is_idle(self) -> bool:
        """
        是否处于空闲状态.
        """
        return self._device_state == DeviceState.IDLE

    def is_listening(self) -> bool:
        """
        是否正在监听.
        """
        return self._device_state == DeviceState.LISTENING

    def is_speaking(self) -> bool:
        """
        是否正在说话.
        """
        return self._device_state == DeviceState.SPEAKING

    # -------------------------
    # 监听模式
    # -------------------------
    @property
    def listening_mode(self) -> ListeningMode:
        """
        获取当前监听模式.
        """
        return self._listening_mode

    def set_listening_mode(self, mode: ListeningMode) -> None:
        """
        设置监听模式.
        """
        self._listening_mode = mode
        logger.debug(f"监听模式设置为: {mode}")

    # -------------------------
    # 会话状态
    # -------------------------
    @property
    def keep_listening(self) -> bool:
        """
        是否保持持续监听.
        """
        return self._keep_listening

    def set_keep_listening(self, value: bool) -> None:
        """
        设置持续监听状态.
        """
        self._keep_listening = value
        logger.debug(f"持续监听: {value}")

    @property
    def aec_enabled(self) -> bool:
        """
        AEC 是否启用.
        """
        return self._aec_enabled

    # -------------------------
    # 中止状态
    # -------------------------
    @property
    def aborted(self) -> bool:
        """
        是否已中止.
        """
        return self._aborted

    def set_aborted(self, value: bool) -> None:
        """
        设置中止状态.
        """
        self._aborted = value

    # -------------------------
    # 复合状态查询
    # -------------------------
    def should_capture_audio(self) -> bool:
        """是否应该采集音频.

        在以下情况下需要采集:
        1. 正在监听且未中止
        2. 正在说话，但启用了 AEC 且在实时模式下保持监听
        """
        if self._device_state == DeviceState.LISTENING and not self._aborted:
            return True

        return (
            self._device_state == DeviceState.SPEAKING
            and self._aec_enabled
            and self._keep_listening
            and self._listening_mode == ListeningMode.REALTIME
        )

    def get_snapshot(self) -> dict:
        """获取状态快照.

        返回当前所有状态的字典，用于调试和日志。
        """
        return {
            "device_state": self._device_state,
            "listening_mode": self._listening_mode,
            "keep_listening": self._keep_listening,
            "aec_enabled": self._aec_enabled,
            "aborted": self._aborted,
        }
