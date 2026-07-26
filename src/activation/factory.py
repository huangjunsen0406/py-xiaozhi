"""按运行模式创建激活 UI（与 create_viewport 对称）."""

from typing import Any


def create_activation_ui(mode: str, activation_service, init_result: dict) -> Any:
    """gui → GuiActivation；tui/cli/gpio → CliActivation.

    Args:
        mode: 运行模式
        activation_service: ActivationService 实例
        init_result: initialize() 结果（避免重复 initialize）
    """
    normalized = (mode or "cli").lower()
    if normalized == "gui":
        from src.ui.gui import GuiActivation

        return GuiActivation(activation_service, init_result)

    # tui / cli / gpio：激活阶段用简单终端交互
    from src.ui.cli import CliActivation

    return CliActivation(activation_service, init_result)
