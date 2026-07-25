# -*- coding: utf-8 -*-
"""激活模块：身份、OTA、HTTP 客户端与 UI 工厂."""

from .factory import create_activation_ui
from .service import ActivationService

__all__ = ["ActivationService", "create_activation_ui"]
