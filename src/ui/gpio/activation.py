# -*- coding: utf-8 -*-
"""GPIO 模式激活流程.

GPIO 模式下的设备激活处理，复用 CLI 激活逻辑。
激活过程通过语音播报提示用户。
"""

from src.logging import get_logger

logger = get_logger()


class GPIOActivation:
    """GPIO 模式激活处理.

    复用 CLI 激活逻辑，通过语音播报引导用户完成激活。
    """

    def __init__(self, activation_service):
        """初始化激活处理.

        Args:
            activation_service: 激活服务实例
        """
        self._service = activation_service

    async def run_activation_process(self) -> bool:
        """运行激活流程.

        Returns:
            激活是否成功
        """
        # 复用 CLI 激活逻辑
        from src.ui.cli import CLIActivation

        logger.info("GPIO 模式：使用 CLI 激活流程")
        cli_activation = CLIActivation(self._service)
        return await cli_activation.run_activation_process()
