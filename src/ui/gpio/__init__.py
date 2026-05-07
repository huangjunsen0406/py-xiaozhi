"""GPIO UI 模块.

提供 GPIO 按键控制界面，仅支持 Linux（树莓派）。

使用时按需导入：
    from src.ui.gpio import GPIOViewManager
"""

from src.ui.gpio.manager import GPIOViewManager

__all__ = ["GPIOViewManager"]
