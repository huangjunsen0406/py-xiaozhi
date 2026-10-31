"""按运行模式创建激活 UI（与 create_viewport 对称）."""

from typing import Any


def create_activation_ui(mode: str, activation_service, init_result: dict) -> Any:
    """gui 使用 GuiActivation，其它模式使用终端激活。"""
    normalized = (mode or "tui").lower()
    if normalized == "gui":
        from src.ui.gui import GuiActivation

        return GuiActivation(activation_service, init_result)

    from src.activation.terminal import TerminalActivation

    return TerminalActivation(activation_service, init_result)
