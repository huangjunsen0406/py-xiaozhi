# Research: Activation/Startup Diff (6cad765 vs HEAD)

- **Query**: Compare activation/startup code between commit 6cad765 (pre-merge main) and current HEAD; identify causes for packaged (.exe) instant failure with empty "系统初始化失败: " message
- **Scope**: internal
- **Date**: 2026-05-15

## Summary of Changes

Between `6cad765` (fix(audio): int16->float32) and current HEAD, the activation/startup subsystem was **entirely rewritten**. Key refactors:

1. `src/core/system_initializer.py` + `src/utils/device_fingerprint.py` + `src/core/ota.py` **replaced** by new `src/activation/service.py` (ActivationService)
2. `src/utils/resource_finder.py` **rewritten** from class-based (ResourceFinder singleton) to function-based module with `platformdirs` dependency
3. Logging moved from `src/utils/logging_config.py` (single file) to `src/logging/` (package with 5 submodules)
4. `src/application.py` (Application class) replaced by `src/bootstrap/container.py` (ServiceContainer)
5. GUI framework changed from PyQt5 to PySide6
6. `config/` directory no longer exists in the repo root (was present at 6cad765)
7. `build.json` name changed from `"小智"` to `"xiaozhi"`

## Findings

### 1. The "系统初始化失败: " Error Location

The error message "系统初始化失败: " maps to this catch block in `src/activation/service.py` line ~170:

```python
except Exception as e:
    self.logger.error(f"系统初始化失败: {e}")
    return ActivationResult(
        success=False,
        need_activation_ui=False,
        message="初始化失败",
        error=str(e),
    )
```

This is inside `ActivationService.initialize()`. The empty exception message means `str(e)` is empty string, which is characteristic of certain import errors or OS-level errors that have no message.

### 2. src/activation/service.py Did NOT Exist at 6cad765

Confirmed: `fatal: path 'src/activation/service.py' exists on disk, but not in '6cad765'`.

At 6cad765, the activation flow was:
- `main.py` -> `handle_activation()` -> `SystemInitializer()` -> `run_initialization()` -> 3 stages (device fingerprint, config management, OTA)
- `SystemInitializer` lived in `src/core/system_initializer.py`
- Device fingerprint was handled by `src/utils/device_fingerprint.py` (separate class)
- OTA was handled by `src/core/ota.py` (separate class)

### 3. Old vs New OTA Config Fetching

**Old flow (6cad765):**
- `SystemInitializer.stage_3_ota_config()` -> `Ota.get_instance()` -> `Ota.fetch_and_update_config()`
- OTA class used `ConfigManager` and `DeviceFingerprint` (both already initialized in stages 1-2)
- Config directory found via `resource_finder.find_config_dir()` which searched multiple paths including `_MEIPASS`

**New flow (HEAD):**
- `ActivationService.initialize()` -> `self._fetch_ota_config()` (method on same class)
- All functionality consolidated into single ActivationService
- Config directory resolved via `get_user_data_dir() / "config"` (user data dir, not install dir)

### 4. Old vs New main.py Startup

**Old (6cad765):**
```python
# Top-level imports (static)
from src.application import Application
from src.utils.logging_config import get_logger, setup_logging

# In __main__:
args = parse_args()
setup_logging()
# ... then GUI/event loop setup
```

**New (HEAD):**
```python
# Top-level (before __main__):
_args = parse_args()                              # Runs at import time
from src.logging import setup_logging             # NEW logging package
setup_logging(enable_console=(_args.mode != "cli"))  # Runs at import time
from src.bootstrap.container import ServiceContainer  # Heavy import
from src.constants.system import SystemConstants
from src.logging import get_logger
logger = get_logger()
```

Critical difference: The new main.py runs `setup_logging()` and imports `ServiceContainer` at **module level** (outside `__main__`), before any try/except protection. Any import failure in the chain crashes without the "系统初始化失败" message -- it would be an unhandled ImportError instead.

### 5. resource_finder.py: PyInstaller Frozen Mode Handling

**Old (6cad765) -- ResourceFinder class:**
```python
def _runtime_base_dir(self) -> Path:
    if self._is_frozen():
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent)).resolve()
    return self._detect_project_root(default=Path(__file__).resolve().parents[2])
```
- In frozen mode: used `_MEIPASS` (PyInstaller temp extraction dir)
- Fallback: `sys.executable` parent directory
- Search paths included: `_MEIPASS`, `exe_dir/_internal`, system install paths, user data dir, CWD
- The `find_config_dir()` searched all these paths for a `config/` directory

**New (HEAD) -- get_app_root() function:**
```python
@lru_cache(maxsize=1)
def get_app_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent.parent
```
- In frozen mode: only uses `sys._MEIPASS` (no fallback to exe parent)
- **No search path mechanism** -- just direct path computation
- `get_user_data_dir()` uses `platformdirs.user_data_dir(get_app_name())`
- `get_config_dir()` returns `get_app_root() / "config"` (read-only install dir)

### 6. New Dependencies Introduced (PyInstaller Risk)

The new code introduces dependencies that must be bundled by PyInstaller:

| Dependency | Used In | Old Code Had It? | PyInstaller Risk |
|---|---|---|---|
| `platformdirs` | `resource_finder.py` (module-level import) | No | HIGH -- imported at module level before any try/except |
| `machineid` (py-machineid) | `activation/service.py` (module-level import) | Yes (in device_fingerprint.py) | MEDIUM -- same as before but now at top of service.py |
| `psutil` | `activation/service.py` (module-level import) | Yes (in device_fingerprint.py) | LOW -- commonly auto-detected |
| `aiohttp` | `activation/service.py` (module-level import) | Yes (in ota.py) | LOW -- commonly auto-detected |
| PySide6 | main.py (conditional import) | No (was PyQt5) | LOW -- conditional import in try/except |

### 7. Likely Root Causes of Packaged Failure

#### Hypothesis A: `platformdirs` Not Bundled (MOST LIKELY)

The import chain at startup is:
1. `main.py` line 55: `from src.logging import setup_logging`
2. `setup_logging()` -> `LoggingConfigManager._load_config()` -> `from src.utils.config_manager import ConfigManager` -> `ConfigManager.__init__()` -> `_init_config_paths()` -> `get_user_data_dir()`
3. `get_user_data_dir()` in `resource_finder.py` line 70: `platformdirs.user_data_dir(get_app_name())`
4. `get_app_name()` -> `SystemConstants.APP_NAME` -> `from src.constants.system import SystemConstants`

If `platformdirs` is not in PyInstaller's hidden imports, this chain fails silently or with an empty ImportError.

**However**, the actual error message is "系统初始化失败: " which comes from inside `ActivationService.initialize()`, meaning the app gets past module-level imports. This means `platformdirs` IS being resolved.

#### Hypothesis B: `machineid` Subprocess Failure in Frozen Mode (VERY LIKELY)

In `ActivationService._get_machine_id()`:
```python
def _get_machine_id(self) -> Optional[str]:
    try:
        return machineid.id()
    except Exception as e:
        self.logger.warning(f"获取 machine_id 失败: {e}")
        return None
```

The `py-machineid` library (v1.0.0) uses subprocess calls to read system machine IDs. On Windows frozen apps, subprocess execution can fail with empty error messages when the PATH is not properly configured or when UAC restricts access. However, this is caught and returns None, so it shouldn't cause the overall failure.

#### Hypothesis C: Empty Exception from OTA Network Call or Config Path Issue (LIKELY)

Inside `ActivationService.initialize()`, the call chain is:
1. `_ensure_device_identity()` -- reads efuse from `get_user_data_dir() / "config" / "efuse.json"`
2. `_initialize_config()` -- initializes ConfigManager
3. `_fetch_ota_config()` -- makes HTTP request

If the OTA URL or DEVICE_ID is None/empty, `_fetch_ota_config()` raises:
```python
if not ota_url or not device_id:
    raise ValueError("OTA URL 或 DEVICE_ID 未配置")
```

This would have a non-empty message. But if the network request fails with a system-level SSL or socket error that has an empty string representation, that could produce the observed "系统初始化失败: " with empty detail.

#### Hypothesis D: Config Migration Failure (LIKELY for fresh installs)

The old code stored `config.json` and `efuse.json` in the bundled `config/` directory (which was writable at `_MEIPASS` or exe directory level). The new code:
1. Looks for config at `get_user_data_dir() / "config"` (e.g., `C:/Users/xxx/AppData/Local/py-xiaozhi/config/`)
2. If not found, tries to migrate from `get_config_dir()` which is `get_app_root() / "config"` = `_MEIPASS/config/`

But `build.json` `add_data` does NOT include `"config:config"`. The bundled data is:
```json
"add_data": ["models:models", "scripts:scripts", "src:src", "libs:libs", "assets:assets"]
```

So on a fresh install, there is NO `config/` in `_MEIPASS`, and no existing user data dir config. The ConfigManager will create a default config, which should work. But the **efuse.json** path in ActivationService uses `get_user_data_dir() / "config"` -- this should also work since it creates the directory.

#### Hypothesis E: `from src.constants.system import SystemConstants` in resource_finder.py (SUBTLE)

The new `resource_finder.py` has a module-level import:
```python
from src.constants.system import SystemConstants
```

In the old code, `resource_finder.py` had NO imports from `src.constants`. This creates a potential circular import or early-execution issue since `resource_finder` is imported by nearly everything.

### 8. The "config/" Directory Missing from Bundled App

At commit 6cad765, a `config/` directory existed in the repo (evidenced by `efuse_file = Path("config") / "efuse.json"` working). The current HEAD has no `config/` directory at the repo root. The `build.json` `add_data` does not include `config:config`.

This means:
- `get_config_dir()` = `_MEIPASS/config/` -- **does not exist** in the packaged app
- Config migration in `ConfigManager._init_config_paths()` finds no source file to copy
- This is handled gracefully (creates default config)

### 9. build.json "name" Change

Old: `"name": "小智"` (Chinese characters)
New: `"name": "xiaozhi"` (ASCII)

This affects the packaged executable name and potentially the `_MEIPASS` path on some systems.

## Files Found

| File Path | Description |
|---|---|
| `main.py` | Entry point -- heavily modified, module-level imports changed |
| `src/activation/__init__.py` | NEW: activation module package init |
| `src/activation/service.py` | NEW: unified ActivationService (replaces SystemInitializer + DeviceFingerprint + Ota) |
| `src/utils/resource_finder.py` | REWRITTEN: class-based -> function-based, adds `platformdirs` dependency |
| `src/utils/config_manager.py` | MODIFIED: uses new resource_finder API, stores config in user data dir |
| `src/logging/__init__.py` | NEW: logging package (replaces `src/utils/logging_config.py`) |
| `src/logging/log_config.py` | NEW: logging configuration with LoggingConfigManager |
| `src/constants/system.py` | MODIFIED: added `APP_DISPLAY_NAME`, version bumped to 2.0.1 |
| `src/bootstrap/container.py` | NEW: ServiceContainer (replaces Application class) |
| `build.json` | MODIFIED: name "小智" -> "xiaozhi", config:config NOT in add_data |

## Key Differences Table

| Aspect | Old (6cad765) | New (HEAD) |
|---|---|---|
| Activation entry | `SystemInitializer` in `src/core/` | `ActivationService` in `src/activation/` |
| Device fingerprint | Separate `DeviceFingerprint` class | Merged into `ActivationService` |
| OTA client | Separate `Ota` class in `src/core/` | Merged into `ActivationService._fetch_ota_config()` |
| Config path resolution | `resource_finder.find_config_dir()` (multi-path search) | `get_user_data_dir() / "config"` (single path) |
| efuse.json location | `config/efuse.json` relative to app or `_MEIPASS` | `get_user_data_dir() / "config" / "efuse.json"` |
| Resource finder | `ResourceFinder` class with `_build_search_dirs()` (6+ paths) | `get_app_root()` function (1 path) |
| New dependencies | None | `platformdirs` (module-level) |
| Logging | `src/utils/logging_config.py` (single file) | `src/logging/` (package, 5 files) |
| GUI framework | PyQt5 | PySide6 |
| build.json name | `"小智"` | `"xiaozhi"` |

## Caveats / Not Found

1. Could not reproduce the packaged build locally -- analysis is based on code reading only
2. The exact empty exception that causes "系统初始化失败: " could not be definitively identified without a stack trace from the packaged build
3. The `unifypy` build tool's internal PyInstaller configuration (hidden imports, hooks) was not inspected -- it may handle `platformdirs` automatically
4. No PyInstaller `.spec` file found in the repo; the build is driven by `unifypy` CLI tool with `build.json`
5. The `config/` directory absence from `add_data` may be intentional (new architecture stores all config in user data dir) but could affect migration from old installations
