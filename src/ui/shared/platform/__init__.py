# -*- coding: utf-8 -*-
"""平台特定代码."""

import sys

if sys.platform == "win32":
    from .windows import apply_window_effects
elif sys.platform == "darwin":
    from .macos import apply_window_effects
else:
    from .linux import apply_window_effects

__all__ = ["apply_window_effects"]
