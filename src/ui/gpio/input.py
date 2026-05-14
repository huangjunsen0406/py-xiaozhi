"""GPIO 输入处理.

封装 gpiozero 按键监听，支持树莓派的 GPIO 按键输入。
仅支持 Linux 系统。

按键模块规格：
- 按下输出低电平（Active Low）
- 松开输出高电平

默认引脚映射（BCM 编号）：
- KEY1: GPIO 17 - 开始/停止对话
- KEY2: GPIO 27 - 中断当前语音
- KEY3: GPIO 22 - 切换自动/手动模式
- KEY4: GPIO 23 - 退出程序

修改 DEFAULT_PINS 可自定义引脚。
"""

import sys
import threading
from typing import Callable, List, Optional

from src.logging import get_logger

logger = get_logger()

# 默认 GPIO 引脚配置（BCM 编号）
# 可根据实际接线修改
DEFAULT_PINS: List[int] = [17, 27, 22, 23]


class GPIOInput:
    """GPIO 按键输入处理类.

    封装 gpiozero 的 Button 类，提供按键事件回调。
    """

    def __init__(
        self,
        pins: Optional[List[int]] = None,
        bounce_time: float = 0.05,
    ):
        """初始化 GPIO 输入.

        Args:
            pins: GPIO 引脚列表（BCM 编号），默认使用 DEFAULT_PINS
            bounce_time: 消抖时间（秒）
        """
        self._pins = pins or DEFAULT_PINS.copy()
        self._bounce_time = bounce_time
        self._buttons: List = []
        self._callbacks: dict[int, dict[str, Optional[Callable]]] = {}
        self._lock = threading.Lock()
        self._available = False

        # 检查平台
        if sys.platform != "linux":
            logger.warning("GPIO 模式仅支持 Linux 系统")
            return

        # 尝试导入 gpiozero
        try:
            from gpiozero import Button  # type: ignore[import-not-found]

            self._Button = Button
            self._available = True
            logger.info(f"GPIO 输入初始化成功，引脚: {self._pins}")
        except ImportError:
            logger.error(
                "未安装 gpiozero 库，请运行: sudo apt install python3-gpiozero python3-rpi.gpio"
            )
        except Exception as e:
            logger.error(f"GPIO 初始化失败: {e}")

    @property
    def available(self) -> bool:
        """GPIO 是否可用."""
        return self._available

    @property
    def pins(self) -> List[int]:
        """当前配置的引脚列表."""
        return self._pins.copy()

    def setup(
        self,
        on_key1_pressed: Optional[Callable] = None,
        on_key2_pressed: Optional[Callable] = None,
        on_key3_pressed: Optional[Callable] = None,
        on_key4_pressed: Optional[Callable] = None,
    ) -> bool:
        """设置按键回调.

        Args:
            on_key1_pressed: KEY1 按下回调
            on_key2_pressed: KEY2 按下回调
            on_key3_pressed: KEY3 按下回调
            on_key4_pressed: KEY4 按下回调

        Returns:
            是否设置成功
        """
        if not self._available:
            logger.warning("GPIO 不可用，跳过按键设置")
            return False

        callbacks = [on_key1_pressed, on_key2_pressed, on_key3_pressed, on_key4_pressed]

        try:
            for i, pin in enumerate(self._pins):
                # 创建按钮实例（Active Low，内部上拉）
                button = self._Button(pin, pull_up=True, bounce_time=self._bounce_time)
                self._buttons.append(button)

                # 保存回调
                with self._lock:
                    self._callbacks[i] = {
                        "pressed": callbacks[i] if i < len(callbacks) else None,
                    }

                # 设置按下回调
                if i < len(callbacks) and callbacks[i]:
                    # 使用闭包捕获索引
                    def make_handler(idx: int):
                        def handler():
                            with self._lock:
                                cb = self._callbacks.get(idx, {}).get("pressed")
                            if cb:
                                logger.debug(f"KEY{idx + 1} (GPIO{self._pins[idx]}) pressed")
                                cb()

                        return handler

                    button.when_pressed = make_handler(i)

                logger.debug(f"KEY{i + 1} -> GPIO{pin} 已配置")

            logger.info(f"GPIO 按键设置完成: {len(self._buttons)} 个按键")
            return True

        except Exception as e:
            logger.error(f"GPIO 按键设置失败: {e}", exc_info=True)
            return False

    def close(self) -> None:
        """关闭 GPIO 资源."""
        for button in self._buttons:
            try:
                button.close()
            except Exception as e:
                logger.warning(f"关闭 GPIO 按钮失败: {e}")

        self._buttons.clear()
        with self._lock:
            self._callbacks.clear()
        logger.info("GPIO 资源已释放")
