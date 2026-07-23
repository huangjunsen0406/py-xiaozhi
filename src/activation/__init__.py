# -*- coding: utf-8 -*-
"""激活模块：设备身份、OTA 校验与激活 UI 工厂."""

from .factory import create_activation_ui
from .service import ActivationService

__all__ = ["ActivationService", "create_activation_ui"]
