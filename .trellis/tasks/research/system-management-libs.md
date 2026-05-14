# Research: Cross-Platform System Management Python Libraries

- **Query**: Python libraries for cross-platform app launching, process management, volume control, and application scanning
- **Scope**: mixed (internal codebase analysis + external library survey)
- **Date**: 2026-05-14

---

## 1. Current Codebase Analysis

### Files Involved

| File Path | Description |
|---|---|
| `src/mcp/tools/system/_tools.py` | MCP tool registration (7 tools: volume get/set/status, app launch/kill/scan/list) |
| `src/mcp/tools/system/tools.py` | Volume get/set/status implementation, delegates to VolumeController |
| `src/mcp/tools/system/app_management/launcher.py` | Unified app launcher dispatcher |
| `src/mcp/tools/system/app_management/killer.py` | Unified app killer dispatcher + running app listing |
| `src/mcp/tools/system/app_management/scanner.py` | Unified installed app scanner dispatcher |
| `src/mcp/tools/system/app_management/utils.py` | AppMatcher class, app cache, find_best_matching_app |
| `src/mcp/tools/system/app_management/_utils.py` | clean_app_name helper |
| `src/mcp/tools/system/app_management/mac/launcher.py` | macOS: subprocess open/osascript |
| `src/mcp/tools/system/app_management/mac/killer.py` | macOS: JXA/ps + kill signals |
| `src/mcp/tools/system/app_management/mac/scanner.py` | macOS: /Applications glob + ps |
| `src/mcp/tools/system/app_management/windows/launcher.py` | Windows: PowerShell, start, os.startfile, registry, UWP |
| `src/mcp/tools/system/app_management/windows/killer.py` | Windows: PowerShell, tasklist, wmic, taskkill |
| `src/mcp/tools/system/app_management/windows/scanner.py` | Windows: Start Menu, registry, PowerShell |
| `src/mcp/tools/system/app_management/linux/launcher.py` | Linux: direct exec, which, xdg-open, .desktop |
| `src/mcp/tools/system/app_management/linux/killer.py` | Linux: ps + kill signals |
| `src/mcp/tools/system/app_management/linux/scanner.py` | Linux: .desktop file parsing + ps |
| `src/utils/volume_controller.py` | Cross-platform volume: pycaw (Win), applescript (mac), pactl/wpctl/amixer (Linux) |

### Current Dependencies (from requirements.txt / pyproject.toml)

- `psutil>=5.9.0` -- already a dependency, but NOT used in app_management (only in `src/activation/service.py`)
- `pycaw>=20230407; sys_platform == "win32"` -- Windows volume control
- `comtypes>=1.4.0; sys_platform == "win32"` -- Required by pycaw
- `applescript>=2021.2.9; sys_platform == "darwin"` -- macOS volume control

### Security Issues in Current Code

**`shell=True` usages** (command injection vectors) in `src/mcp/tools/system/app_management/windows/launcher.py`:
- Line 104: `subprocess.run(powershell_cmd, shell=True, ...)` in `_try_powershell_start` -- app_name partially escaped but still uses shell
- Line 118: `subprocess.run(start_cmd, shell=True, ...)` in `_try_start_command` -- f-string with user input
- Line 178: `subprocess.run(f"where {app_name}", shell=True, ...)` in `_try_where_command` -- raw f-string injection

**Unescaped string interpolation into shell commands**:
- `windows/launcher.py` line 297: PowerShell script uses f-string interpolation of `app_name` into PowerShell code in `_launch_uwp_app`
- `mac/launcher.py` line 51: `osascript -e f'tell application "{app_name}" to activate'` -- AppleScript injection

### Pattern Summary

The current implementation uses 18 Python files with ~1500 lines of custom platform-specific code. Each platform (mac/windows/linux) has its own launcher, killer, and scanner module. Process listing on all platforms relies on shelling out to OS commands (`ps`, `tasklist`, `wmic`, PowerShell) rather than using `psutil` which is already a dependency.

---

## 2. Library Analysis

### 2.1 psutil (Process and System Utilities)

- **PyPI**: `psutil`
- **Current version**: 6.1.1 (as of late 2024, actively maintained)
- **Maintainer**: Giampaolo Rodola (active since 2009)
- **License**: BSD-3-Clause

**Capabilities covered**:

| Capability | Covered? | Details |
|---|---|---|
| App launching | NO | Not in scope |
| App killing | YES | `psutil.Process(pid).terminate()` / `.kill()` -- cross-platform, no subprocess |
| Installed app scanning | NO | Not in scope |
| Running process listing | YES | `psutil.process_iter(['pid', 'name', 'exe', 'cmdline', 'status'])` -- cross-platform |
| Volume control | NO | Not in scope |

**Cross-platform**: macOS, Windows, Linux, FreeBSD, OpenBSD, NetBSD, Sun Solaris, AIX

**Security**: Does NOT use `shell=True`. Uses direct C-extension bindings to OS APIs (sysctl on BSD, /proc on Linux, Windows API on Windows). No command injection risk.

**Key advantages over current code**:
- `psutil.process_iter()` replaces all custom `ps`, `tasklist`, `wmic`, JXA, and PowerShell process-listing code across 3 platforms
- `psutil.Process(pid).terminate()` / `.kill()` replaces all custom `kill -15/-9` and `taskkill` code
- `psutil.Process(pid).children(recursive=True)` handles process tree killing (replacing Windows `_kill_by_process_groups`)
- Already a project dependency (`psutil>=5.9.0`)

**API examples relevant to this codebase**:
```python
# List running processes (replaces all 3 platform list_running_applications)
for proc in psutil.process_iter(['pid', 'name', 'exe', 'cmdline', 'status']):
    info = proc.info
    # info['pid'], info['name'], info['exe'], info['cmdline']

# Kill a process (replaces mac/linux kill + windows taskkill)
p = psutil.Process(pid)
p.terminate()  # SIGTERM / TerminateProcess
p.kill()       # SIGKILL / TerminateProcess

# Kill process tree (replaces Windows _kill_by_process_groups)
parent = psutil.Process(pid)
children = parent.children(recursive=True)
for child in children:
    child.terminate()
parent.terminate()

# Check if process is running
psutil.pid_exists(pid)
```

---

### 2.2 subprocess (stdlib) -- for App Launching

- **PyPI**: N/A (stdlib)
- **Part of**: Python standard library

**Capabilities covered**:

| Capability | Covered? | Details |
|---|---|---|
| App launching | PARTIAL | Platform-specific commands still needed |
| App killing | YES | But psutil is better |
| Installed app scanning | PARTIAL | Registry/desktop file queries |
| Running process listing | PARTIAL | But psutil is better |
| Volume control | PARTIAL | CLI tools |

**Notes**: App launching inherently requires platform-specific mechanisms. There is no single cross-platform Python API to "launch a desktop application by name." However, the security of subprocess usage can be improved:
- Always use list form: `subprocess.run(["open", "-a", app_name])` (no shell=True)
- Never interpolate user input into shell command strings

---

### 2.3 pycaw (Python Core Audio Windows)

- **PyPI**: `pycaw`
- **Current version**: 20230407 (last release April 2023)
- **Maintainer**: AndreMiras
- **License**: MIT
- **Already used**: Yes, in `src/utils/volume_controller.py`

**Capabilities covered**:

| Capability | Covered? | Details |
|---|---|---|
| Volume control (Windows) | YES | Full Windows Core Audio API access |

**Cross-platform**: Windows ONLY

**Security**: No subprocess calls. Uses COM/ctypes to directly access Windows Core Audio API.

**Notes**: This is the standard Python library for Windows volume control. Already in use and appropriate.

---

### 2.4 applescript (Python AppleScript bridge)

- **PyPI**: `applescript`
- **Current version**: 2021.2.9 (last release Feb 2021)
- **Maintainer**: rdhyee
- **License**: MIT
- **Already used**: Yes, in `src/utils/volume_controller.py`

**Capabilities covered**:

| Capability | Covered? | Details |
|---|---|---|
| Volume control (macOS) | YES | Via AppleScript `set volume output volume N` |
| App launching (macOS) | POSSIBLE | Via `tell application "X" to activate` |
| App killing (macOS) | POSSIBLE | Via `tell application "X" to quit` |

**Cross-platform**: macOS ONLY

**Security**: The library itself does not use `shell=True`, but AppleScript commands that include unsanitized user input can lead to AppleScript injection. Current code at `mac/launcher.py:51` has this issue.

**Notes**: Maintenance appears dormant (no releases since 2021). The library works but is a thin wrapper. An alternative is using `subprocess.run(["osascript", "-e", script])` directly.

---

### 2.5 pulsectl / pulsectl-asyncio

- **PyPI**: `pulsectl` / `pulsectl-asyncio`
- **Current version**: pulsectl 24.6.0 (June 2024), pulsectl-asyncio 1.2.1 (2024)
- **Maintainer**: mk-fg (pulsectl), mhthies (pulsectl-asyncio)
- **License**: MIT

**Capabilities covered**:

| Capability | Covered? | Details |
|---|---|---|
| Volume control (Linux) | YES | Native PulseAudio ctypes bindings (no subprocess) |

**Cross-platform**: Linux ONLY (PulseAudio-based systems)

**Security**: Uses ctypes bindings to libpulse. No subprocess calls. No command injection risk.

**Advantages over current code**: The current Linux volume control shells out to `pactl`, `wpctl`, or `amixer` via subprocess. `pulsectl` provides a direct Python API to PulseAudio without spawning processes.

**Limitation**: Only works with PulseAudio. Does not support PipeWire natively (though PipeWire often provides PulseAudio compatibility). Does not support ALSA-only systems.

**API example**:
```python
import pulsectl
with pulsectl.Pulse('volume-control') as pulse:
    sink = pulse.sink_list()[0]  # default sink
    volume = pulse.volume_get_all_chans(sink)  # 0.0 - 1.0
    pulse.volume_set_all_chans(sink, 0.5)  # set to 50%
    pulse.mute(sink, mute=True)  # mute
```

---

### 2.6 osascript (macOS only -- alternative to applescript package)

- **PyPI**: `osascript`
- **Current version**: 2020.12.3 (December 2020)
- **License**: MIT

**Notes**: Another thin wrapper around macOS osascript. Even less maintained than `applescript`. Not recommended as a replacement.

---

### 2.7 desktop-notifier / plyer (cross-platform desktop interaction)

- **PyPI**: `plyer`
- **Current version**: 2.1.0 (2023)
- **Maintainer**: Kivy team
- **License**: MIT

**Capabilities covered**:

| Capability | Covered? | Details |
|---|---|---|
| App launching | NO | Not in scope |
| App killing | NO | Not in scope |
| Volume control | NO | Not in scope |
| Installed app scanning | NO | Not in scope |

**Notes**: plyer provides cross-platform access to hardware features (battery, GPS, notifications, camera, etc.) but does NOT cover app management, process management, or volume control. Not useful for this use case.

---

### 2.8 pyaudio / sounddevice

- **PyPI**: `pyaudio` / `sounddevice`
- **Focus**: Audio stream recording/playback, NOT system volume control
- **Notes**: These libraries handle audio I/O streams, not system volume levels. Not relevant.

---

### 2.9 comtypes

- **PyPI**: `comtypes`
- **Current version**: 1.4.8 (2024, actively maintained)
- **Already used**: Yes, required by pycaw
- **Notes**: General-purpose COM interface library for Windows. Used as a dependency of pycaw for Windows volume control.

---

### 2.10 AppKit (pyobjc-framework-Cocoa) -- macOS

- **PyPI**: `pyobjc-framework-Cocoa`
- **Current version**: 11.0 (2025, actively maintained)
- **Maintainer**: Ronald Oussoren
- **License**: MIT

**Capabilities covered**:

| Capability | Covered? | Details |
|---|---|---|
| App launching (macOS) | YES | `NSWorkspace.sharedWorkspace().launchApplication_(name)` |
| App killing (macOS) | PARTIAL | Can get running app list, send terminate |
| Installed app scanning (macOS) | PARTIAL | Can enumerate /Applications |
| Running process listing (macOS) | YES | `NSWorkspace.sharedWorkspace().runningApplications()` |
| Volume control | NO | Not directly |

**Cross-platform**: macOS ONLY

**Security**: Native Objective-C bridge. No subprocess calls for app launching. No command injection risk.

**Notes**: The current macOS killer code (`mac/killer.py`) already uses JXA to call `NSWorkspace.sharedWorkspace.runningApplications` via osascript. Using pyobjc directly would eliminate the subprocess call. However, this adds a heavy dependency (pyobjc) and only helps on macOS. Using psutil for process listing is simpler and cross-platform.

---

## 3. Summary: Coverage Matrix

| Capability | psutil | subprocess (stdlib) | pycaw | applescript | pulsectl | pyobjc |
|---|---|---|---|---|---|---|
| App launching | -- | Platform-specific | -- | macOS only | -- | macOS only |
| App killing/closing | ALL platforms | Platform-specific | -- | macOS only | -- | macOS only |
| Installed app scanning | -- | Platform-specific | -- | -- | -- | macOS only |
| Running process listing | ALL platforms | Platform-specific | -- | -- | -- | macOS only |
| Volume control | -- | -- | Windows | macOS | Linux (PulseAudio) | -- |

---

## 4. Recommended Library Combinations (by capability)

### Process Management (kill + list running)

**Best option: `psutil`** (already a dependency)
- Replaces ALL custom process listing code across mac/windows/linux (3 killer modules + 3 scanner modules for running apps)
- Replaces ALL custom process killing code across mac/windows/linux
- No `shell=True`, no subprocess, no command injection risk
- Single API for all platforms

### App Launching

**No single cross-platform library exists.** App launching requires platform-specific mechanisms:
- macOS: `open -a <name>` or `NSWorkspace.launchApplication_()`
- Windows: `os.startfile()`, `subprocess.Popen(["start", ...])`, registry lookup
- Linux: `subprocess.Popen([name])`, `xdg-open`, `.desktop` file launching via `gtk-launch`

The current approach of platform-specific launchers is fundamentally correct. The security fix is to eliminate `shell=True` and sanitize inputs to osascript/PowerShell.

### Installed App Scanning

**No cross-platform library exists.** This inherently requires platform-specific logic:
- macOS: Glob `/Applications/*.app`
- Windows: Registry + Start Menu shortcuts
- Linux: Parse `.desktop` files

The current approach is fundamentally correct.

### Volume Control

**Current stack is already optimal:**
- Windows: `pycaw` (already used, direct COM API, no subprocess)
- macOS: `applescript` package (already used)
- Linux: subprocess calls to `pactl`/`wpctl`/`amixer` (could be replaced by `pulsectl` for PulseAudio systems, but that would lose wpctl/amixer support)

---

## 5. Key Files with `shell=True` (Security Vulnerabilities)

| File | Line | Code | Risk |
|---|---|---|---|
| `windows/launcher.py` | 104 | `subprocess.run(powershell_cmd, shell=True, ...)` | app_name in PowerShell command |
| `windows/launcher.py` | 118 | `subprocess.run(start_cmd, shell=True, ...)` | app_name in start command |
| `windows/launcher.py` | 178 | `subprocess.run(f"where {app_name}", shell=True, ...)` | raw app_name injection |
| `windows/launcher.py` | 296-310 | PowerShell f-string with `{app_name}` | PowerShell injection in UWP launch |
| `mac/launcher.py` | 51 | `f'tell application "{app_name}" to activate'` | AppleScript injection |

---

## Caveats / Not Found

- **No unified "system management" library** exists that covers all 5 capabilities cross-platform. The landscape is fragmented by design because OS APIs differ fundamentally.
- **pulsectl** would only help if the project is willing to drop support for ALSA-only and PipeWire-only (without PulseAudio compat) Linux systems.
- **pyobjc** is very large (~100+ sub-packages) and would be overkill just for app launching on macOS.
- **psutil is already a project dependency** but is completely unused in the app management code. This is the single biggest improvement opportunity -- it can eliminate most of the custom subprocess-based process listing and killing code.
- The `applescript` package has not been updated since 2021. It still works but may need monitoring for macOS compatibility.
