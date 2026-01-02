# -*- coding: utf-8 -*-
"""GPIO 视图管理器.

管理 GPIO 模式下的按键输入和状态显示（通过日志）。
与 CLI 的 CLIViewManager 功能对应。
"""

import asyncio
from typing import TYPE_CHECKING, Optional

from src.core.event_bus import EventBus, Events
from src.logging import get_logger

from .input import GPIOInput

if TYPE_CHECKING:
    pass

logger = get_logger()


class GPIOViewManager:
    """GPIO 视图管理器.

    管理 GPIO 模式下的按键输入，提供与 CLI ViewManager 一致的接口。
    状态通过日志输出，无终端交互界面。
    """

    def __init__(self, event_bus: EventBus):
        self._event_bus = event_bus
        self._gpio_input = GPIOInput()
        self._running = False
        self._loop: Optional[asyncio.AbstractEventLoop] = None

        # 状态
        self._auto_mode = False
        self._status = "待命"
        self._connected = False
        self._tts_text = ""

        # 订阅事件
        self._subscribe_events()

    def _subscribe_events(self):
        """订阅 EventBus 事件."""
        self._event_bus.on(Events.UI_UPDATE_TEXT, self._on_update_text)
        self._event_bus.on(Events.UI_UPDATE_EMOTION, self._on_update_emotion)
        self._event_bus.on(Events.UI_UPDATE_STATUS, self._on_update_status)
        logger.debug("GPIOViewManager: 已订阅 UI 事件")

    async def _on_update_text(self, data):
        """处理文本更新."""
        text = data.text if hasattr(data, "text") else str(data)
        self._tts_text = text
        logger.info(f"[TTS] {text}")

    async def _on_update_emotion(self, data):
        """处理表情更新."""
        emotion = data.emotion if hasattr(data, "emotion") else str(data)
        logger.debug(f"[表情] {emotion}")

    async def _on_update_status(self, data):
        """处理状态更新."""
        if hasattr(data, "status"):
            self._status = data.status
            self._connected = getattr(data, "connected", True)
        elif isinstance(data, dict):
            self._status = data.get("status", "")
            self._connected = data.get("connected", True)
        logger.info(f"[状态] {self._status} (连接: {'是' if self._connected else '否'})")

    async def start(self, mode: str = "gpio"):
        """启动 GPIO 视图.

        Args:
            mode: 运行模式（GPIO 模式下忽略此参数）
        """
        logger.info("GPIOViewManager: 启动 GPIO 界面...")
        self._running = True
        self._loop = asyncio.get_running_loop()

        # 设置 GPIO 按键回调
        if self._gpio_input.available:
            self._gpio_input.setup(
                on_key1_pressed=self._on_key1,
                on_key2_pressed=self._on_key2,
                on_key3_pressed=self._on_key3,
                on_key4_pressed=self._on_key4,
            )
            logger.info("GPIO 按键已就绪")
            logger.info("KEY1: 开始/停止对话")
            logger.info("KEY2: 中断语音")
            logger.info("KEY3: 切换模式")
            logger.info("KEY4: 退出程序")
        else:
            logger.warning("GPIO 不可用，按键功能已禁用")

        # 保持运行（事件驱动）
        try:
            while self._running:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            logger.info("GPIOViewManager: 任务被取消")

    async def close(self):
        """关闭 GPIO 视图."""
        logger.info("GPIOViewManager: 正在关闭...")
        self._running = False

        # 取消订阅事件
        try:
            self._event_bus.off(Events.UI_UPDATE_TEXT, self._on_update_text)
            self._event_bus.off(Events.UI_UPDATE_EMOTION, self._on_update_emotion)
            self._event_bus.off(Events.UI_UPDATE_STATUS, self._on_update_status)
        except Exception as e:
            logger.warning(f"GPIOViewManager: 取消订阅失败: {e}")

        # 关闭 GPIO
        self._gpio_input.close()
        logger.info("GPIOViewManager: 已关闭")

    # ========== 按键回调 ==========

    def _on_key1(self):
        """KEY1: 开始/停止对话（根据当前模式）."""
        if self._auto_mode:
            # 自动模式：开始/停止自动对话
            self._safe_emit(Events.UI_AUTO_START)
            logger.info("[KEY1] 自动模式：开始对话")
        else:
            # 手动模式：切换录音状态
            self._safe_emit(Events.UI_MANUAL_TOGGLE)
            logger.info("[KEY1] 手动模式：切换录音")

    def _on_key2(self):
        """KEY2: 中断当前语音."""
        self._safe_emit(Events.UI_ABORT_REQUEST)
        logger.info("[KEY2] 中断语音")

    def _on_key3(self):
        """KEY3: 切换自动/手动模式."""
        self._safe_emit(Events.UI_AUTO_TOGGLE)
        new_mode = not self._auto_mode
        mode_text = "自动" if new_mode else "手动"
        logger.info(f"[KEY3] 切换到{mode_text}模式")

    def _on_key4(self):
        """KEY4: 退出程序."""
        self._safe_emit(Events.UI_QUIT_REQUEST)
        logger.info("[KEY4] 退出程序")

    def _safe_emit(self, event: str, data=None):
        """安全地发送事件."""
        if self._loop and self._loop.is_running():
            if data is None:
                self._loop.call_soon_threadsafe(
                    lambda: asyncio.create_task(self._event_bus.emit(event))
                )
            else:
                self._loop.call_soon_threadsafe(
                    lambda e=event, d=data: asyncio.create_task(self._event_bus.emit(e, d))
                )

    # ========== 公共 API ==========

    @property
    def is_running(self) -> bool:
        """是否正在运行."""
        return self._running

    def set_status(self, status: str, connected: bool = True):
        """设置状态."""
        self._status = status
        self._connected = connected
        logger.info(f"[状态] {status}")

    def set_tts_text(self, text: str):
        """设置 TTS 文本."""
        self._tts_text = text
        logger.info(f"[TTS] {text}")

    def set_emotion(self, emotion: str):
        """设置表情."""
        logger.debug(f"[表情] {emotion}")

    def set_auto_mode(self, auto_mode: bool):
        """设置自动模式."""
        self._auto_mode = auto_mode
        mode_text = "自动" if auto_mode else "手动"
        logger.info(f"[模式] {mode_text}")

    # ========== 兼容 GUI ViewManager 的属性 ==========

    @property
    def main_model(self):
        """返回自身作为 model 代理."""
        return self

    def toggle_auto_mode(self):
        """切换自动模式."""
        self._auto_mode = not self._auto_mode
        mode_text = "自动" if self._auto_mode else "手动"
        logger.info(f"[模式] {mode_text}")
