# Task 4 Learnings: QTranslator Loading in main.py

## What Was Done
- Added QTranslator loading with --lang CLI argument support to main.py
- Fallback chain: target_lang → en_US → zh_CN

## Key Patterns Found

### QTranslator Loading Pattern (from Qt docs)
```python
from PyQt5.QtCore import QLocale, QTranslator

translator = QTranslator()
if translator.load(qm_path):
    qt_app.installTranslator(translator)
```

### System Locale Detection
```python
target_lang = QLocale.system().name()  # Returns e.g. "en_US", "zh_CN"
```

### Translation File Path Convention
- Path: `i18n/translations/xiaozhi_{locale}.qm`
- Example: `xiaozhi_en_US.qm`, `xiaozhi_zh_CN.qm`

## Issues Encountered
- PyQt5 import errors shown by lsp_diagnostics are false positives (imports work at runtime with proper environment)
- Translation files don't exist yet in i18n/translations/ (infrastructure only)

## Config Manager Usage
```python
from src.utils.config_manager import ConfigManager
config_mgr = ConfigManager.get_instance()
config_mgr.update_config("SYSTEM_OPTIONS.LANGUAGE", target_lang)
```
