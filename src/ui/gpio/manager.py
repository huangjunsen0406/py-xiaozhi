# -*- coding: utf-8 -*-
"""GPIO 按键界面（状态打日志）."""

import asyncio
from typing import TYPE_CHECKING, Optional

from src.core.event_bus import EventBus, Events
from src.logging import get_logger

from .input import GPIOInput

if TYPE_CHECKING:
    from src.core.task_manager import TaskManager

logger = get_logger()


class GPIOViewManager:
    """GPIO 界面（接口和 CLI 对齐）."""

    def __init__(
        self,
        event_bus: EventBus,
        task_manager: Optional["TaskManager"] = None,
    ):
        self._event_bus = event_bus
        self._task_manager = task_manager
        self._gpio_input = GPIOInput()
        self._running = False
        self._loop: Optional[asyncio.AbstractEventLoop] = None

        # 状态
        self._auto_mode = False
        self._status = "待命"
        self._connected = False
        self._chat_text = ""
        self._music_line = ""

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
        self._gpio_input.close()
        logger.info("GPIOViewManager: 已关闭")

    # ========== 按键回调 ==========

    def _on_key1(self):
        """KEY1: 开始/停止对话."""
        if self._auto_mode:
            self._safe_emit(Events.UI_AUTO_START)
            logger.info("[KEY1] 自动模式：切换开始/停止对话")
        else:
            self._safe_emit(Events.UI_MANUAL_TOGGLE)
            logger.info("[KEY1] 手动模式：切换录音")

    def _on_key2(self):
        """KEY2: 打断."""
        self._safe_emit(Events.UI_ABORT_REQUEST)
        logger.info("[KEY2] 中断语音")

    def _on_key3(self):
        """KEY3: 切自动/手动."""
        self._safe_emit(Events.UI_AUTO_TOGGLE)
        logger.info("[KEY3] 请求切换对话模式")

    def _on_key4(self):
        """KEY4: 退出程序."""
        self._safe_emit(Events.UI_QUIT_REQUEST)
        logger.info("[KEY4] 退出程序")

    def _safe_emit(self, event: str, data=None):
        """安全地发送事件.

        优先经 TaskManager.schedule_nowait（线程安全 + 可追踪）；
        否则回退 run_coroutine_threadsafe。
        """
        def _start_emit():
            if data is None:
                return self._event_bus.emit(event)
            return self._event_bus.emit(event, data)

        if self._task_manager is not None:
            try:
                self._task_manager.schedule_nowait(_start_emit)
                return
            except Exception as e:
                logger.error(
                    f"GPIOViewManager 经 TaskManager 调度事件 {event} 失败: {e}",
                    exc_info=True,
                )

        if not self._loop or not self._loop.is_running():
            return
        coro = _start_emit()
        try:
            fut = asyncio.run_coroutine_threadsafe(coro, self._loop)

            def _done(f):
                try:
                    exc = f.exception()
                except Exception:
                    return
                if exc:
                    logger.error(
                        f"GPIOViewManager 发射事件 {event} 失败: {exc}",
                        exc_info=exc,
                    )

            fut.add_done_callback(_done)
        except Exception as e:
            logger.error(f"GPIOViewManager 调度事件 {event} 失败: {e}", exc_info=True)
            if asyncio.iscoroutine(coro):
                coro.close()

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

    def set_chat_text(self, text: str):
        self._chat_text = text
        logger.info(f"[对话] {text}")

    def set_music_line(self, text: str):
        self._music_line = text
        logger.info(f"[音乐] {text}")

    def set_emotion(self, emotion: str):
        logger.debug(f"[表情] {emotion}")

    def set_auto_mode(self, auto_mode: bool):
        # KEY1 分支会看这个
        self._auto_mode = auto_mode
        mode_text = "自动" if auto_mode else "手动"
        logger.info(f"[模式] {mode_text}")

    def set_button_text(self, text: str):
        logger.debug(f"GPIO set_button_text: {text}")

    def is_auto_mode(self) -> bool:
        return bool(self._auto_mode)
