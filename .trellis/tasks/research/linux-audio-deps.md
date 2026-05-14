# Research: Linux Audio System Dependencies by Distro Version

- **Query**: Correct audio-related system package names for Ubuntu 20.04/22.04/24.04/25.04 and Raspberry Pi OS (Bookworm/Bullseye)
- **Scope**: mixed (internal codebase + external package repositories)
- **Date**: 2026-05-14

## Summary of Current Codebase State

The project's install guide (`documents/docs/guide/系统依赖安装.md`, line 46-51) currently recommends:
```bash
sudo apt-get install -y \
    portaudio19-dev libportaudio2 \
    ffmpeg libopus0 libopus-dev \
    libasound2-dev \
    libxcb-xinerama0 libxkbcommon-x11-0 \
    build-essential python3-venv python3-pip
```

The troubleshooting doc (`documents/docs/guide/异常汇总.md`, line 452-454) also references `portaudio19-dev`, `libportaudio2`, `libasound2-dev`.

---

## Question 1: `libasound2-dev` vs `libasound-dev`

### Finding

Starting with Ubuntu 24.04 (Noble Numbat) and Debian Bookworm (12), the ALSA development headers package was **renamed** from `libasound2-dev` to `libasound-dev`. The package `libasound2-dev` still exists as a **transitional package** that depends on `libasound-dev`, so using the old name still works but may emit deprecation warnings or disappear in future releases.

| Distro Version | Package Name | Notes |
|---|---|---|
| Ubuntu 20.04 (Focal) | `libasound2-dev` | Only this name exists |
| Ubuntu 22.04 (Jammy) | `libasound2-dev` | Only this name exists |
| Ubuntu 24.04 (Noble) | `libasound-dev` (canonical), `libasound2-dev` (transitional) | Both work; new name preferred |
| Ubuntu 25.04 (Plucky) | `libasound-dev` (canonical), `libasound2-dev` (transitional) | Both work; transitional may be removed eventually |
| RPi OS Bullseye (Debian 11) | `libasound2-dev` | Only this name exists |
| RPi OS Bookworm (Debian 12) | `libasound-dev` (canonical), `libasound2-dev` (transitional) | Both work |

### Recommendation for Install Script

Use a conditional or fallback approach:
```bash
sudo apt-get install -y libasound2-dev 2>/dev/null || sudo apt-get install -y libasound-dev
```
Or simply use `libasound2-dev` which still resolves on all versions due to the transitional package. For forward-compatibility, prefer `libasound-dev` on 24.04+.

---

## Question 2: Default Audio Server per Version

| Distro Version | Default Audio Server | Notes |
|---|---|---|
| Ubuntu 20.04 (Focal) | **PulseAudio** | PipeWire not available by default |
| Ubuntu 22.04 (Jammy) | **PipeWire** (with pipewire-pulse compatibility) | PipeWire replaced PulseAudio as default in desktop installs. Server/minimal installs may have neither. |
| Ubuntu 24.04 (Noble) | **PipeWire** (with pipewire-pulse) | PipeWire is standard. Full PipeWire-native session. |
| Ubuntu 25.04 (Plucky) | **PipeWire** (with pipewire-pulse) | PipeWire is standard. |
| RPi OS Bullseye (Debian 11) | **PulseAudio** (desktop), **ALSA only** (Lite) | `pulseaudio` pre-installed on desktop image |
| RPi OS Bookworm (Debian 12) | **PipeWire** (with pipewire-pulse, desktop), **ALSA only** (Lite) | RPi OS Bookworm desktop switched to PipeWire. Lite has no audio server. |

### Key Insight

The existing FAQ (`documents/docs/guide/异常汇总.md`, line 519-522) already mentions this partially:
> Ubuntu 20.04: PulseAudio  
> Ubuntu 22.04+: PipeWire (compatible with PulseAudio)

This is correct. The install guide should not recommend `pulseaudio` installation on 22.04+ since PipeWire is already running and installing standalone PulseAudio can cause conflicts.

---

## Question 3: PipeWire's PulseAudio Compatibility Layer (`pactl`)

For the `pactl` command to work on PipeWire systems, the following packages are needed:

| Distro Version | Package for `pactl` | Notes |
|---|---|---|
| Ubuntu 20.04 | `pulseaudio-utils` | Native PulseAudio, pactl comes with it |
| Ubuntu 22.04 | `pipewire-pulse` + `pulseaudio-utils` | `pipewire-pulse` provides the PulseAudio server emulation; `pulseaudio-utils` provides the `pactl` CLI binary |
| Ubuntu 24.04/25.04 | `pipewire-pulse` + `pulseaudio-utils` | Same as 22.04. On desktop installs both are pre-installed. |
| RPi OS Bookworm (desktop) | `pipewire-pulse` + `pulseaudio-utils` | Pre-installed on desktop image |
| RPi OS Bullseye | `pulseaudio-utils` | Native PulseAudio |

### Important Note

On PipeWire systems, do NOT install the `pulseaudio` daemon package (just `pulseaudio-utils` for the CLI tools). Installing the full `pulseaudio` package can conflict with `pipewire-pulse`.

The project code in `src/mcp/tools/system/volume_controller.py` uses `pactl` for volume control, so `pulseaudio-utils` is needed universally. The install script should install:
- `pulseaudio-utils` (for `pactl` binary) on all versions
- NOT `pulseaudio` (the daemon) on 22.04+ where PipeWire is default

---

## Question 4: `portaudio19-dev` Availability

| Distro Version | `portaudio19-dev` available? | Notes |
|---|---|---|
| Ubuntu 20.04 (Focal) | Yes | Package version ~19.6.0 |
| Ubuntu 22.04 (Jammy) | Yes | Package version ~19.6.0 |
| Ubuntu 24.04 (Noble) | Yes | Package version ~19.6.0 |
| Ubuntu 25.04 (Plucky) | Yes | Package version ~19.6.0 |
| RPi OS Bullseye | Yes | Available in Debian repos |
| RPi OS Bookworm | Yes | Available in Debian repos |

`portaudio19-dev` exists across all target platforms. The companion runtime library `libportaudio2` is also available on all versions.

No package rename has occurred for PortAudio.

---

## Question 5: `libopus0` vs `libopus-dev`

Both packages serve different purposes:
- `libopus0`: Runtime shared library (`libopus.so.0`)
- `libopus-dev`: Development headers + pkg-config file (for compiling software that links against opus)

| Distro Version | `libopus0` | `libopus-dev` | Opus version |
|---|---|---|---|
| Ubuntu 20.04 | Yes | Yes | 1.3.1 |
| Ubuntu 22.04 | Yes | Yes | 1.3.1 |
| Ubuntu 24.04 | Yes | Yes | 1.4+ |
| Ubuntu 25.04 | Yes | Yes | 1.5+ |
| RPi OS Bullseye | Yes | Yes | 1.3.1 |
| RPi OS Bookworm | Yes | Yes | 1.4+ |

### What py-xiaozhi Actually Needs

Looking at `src/utils/opus_loader.py` (line 32-36), the project loads `libopus.so.0` at runtime via `ctypes.CDLL`. It does NOT compile against opus headers. Therefore:
- `libopus0` (runtime library) is **required**
- `libopus-dev` (development headers) is **optional** -- only needed if building opuslib from source or other C extensions

The project also bundles opus binaries in `libs/libopus/linux/arm64/libopus.so` and `libs/libopus/linux/x64/libopus.so` as fallbacks.

### Recommendation

Install both `libopus0` and `libopus-dev` (current behavior is correct). The dev package is small and ensures the system is set up for any potential compilation needs.

---

## Question 6: Raspberry Pi OS Audio Packages

### RPi OS Bookworm Desktop (Default Image)

**Pre-installed audio packages:**
- `alsa-utils` (aplay, arecord, amixer, etc.)
- `libasound2` (ALSA runtime library)
- `pipewire`, `pipewire-pulse`, `wireplumber` (PipeWire audio server + session manager)
- `pulseaudio-utils` (pactl command, via PipeWire compatibility)

**Needs manual installation:**
- `portaudio19-dev` -- NOT pre-installed
- `libportaudio2` -- NOT pre-installed
- `libopus0` -- NOT pre-installed
- `libopus-dev` -- NOT pre-installed  
- `ffmpeg` -- NOT pre-installed
- `libasound2-dev` / `libasound-dev` -- NOT pre-installed (development headers)
- `build-essential` -- NOT pre-installed
- `python3-venv` -- NOT pre-installed (Python venv module)

### RPi OS Bookworm Lite (Headless)

**Pre-installed audio packages:**
- `alsa-utils` (basic ALSA tools)
- `libasound2`

**Needs manual installation (everything else):**
- All of the above, PLUS:
- `pipewire`, `pipewire-pulse`, `wireplumber` OR `pulseaudio` (no audio server by default on Lite)

### RPi OS Bullseye Desktop

**Pre-installed:**
- `alsa-utils`, `libasound2`
- `pulseaudio`, `pulseaudio-utils`

**Needs manual installation:**
- `portaudio19-dev`, `libportaudio2`, `libopus0`, `libopus-dev`, `ffmpeg`, `libasound2-dev`, `build-essential`

### GPIO / gpiozero Dependencies (for GPIO mode)

From `src/ui/gpio/input.py` (line 69) and `documents/docs/guide/开发指南.md` (line 253-256):
```bash
sudo apt install python3-gpiozero python3-rpi.gpio
sudo apt install -y python3-lgpio || true
```
- `python3-gpiozero` is pre-installed on RPi OS Desktop
- `python3-rpi.gpio` is pre-installed on RPi OS Desktop
- `python3-lgpio` may need manual install

---

## Question 7: Python 3.10+ on Ubuntu 20.04

Ubuntu 20.04 (Focal) ships with **Python 3.8** as the default system Python. It does NOT include Python 3.10+ in the official repositories.

### Options to Get Python 3.10+ on Ubuntu 20.04

1. **deadsnakes PPA** (most common approach):
   ```bash
   sudo add-apt-repository ppa:deadsnakes/ppa
   sudo apt update
   sudo apt install python3.10 python3.10-venv python3.10-dev
   ```

2. **pyenv** (user-space Python version manager):
   ```bash
   curl https://pyenv.run | bash
   pyenv install 3.10.14
   ```

3. **uv** (can manage Python versions):
   ```bash
   uv python install 3.10
   ```

4. **Build from source** (not recommended for most users)

### Implications for the Project

The project requires Python >= 3.10 (per `documents/docs/guide/系统依赖安装.md`, line 9). Ubuntu 20.04 users will always need a PPA or version manager. The README.md (line 109) says "Python Version: 3.9 - 3.12" but the install guide says ">= 3.10" -- there is a minor inconsistency here that should be resolved.

### Note on EOL

Ubuntu 20.04 LTS standard support ended April 2025. Extended Security Maintenance (ESM) continues, but many users will be on 22.04+ by now. Supporting 20.04 adds complexity.

---

## Question 8: sounddevice / PortAudio Issues on ARM (aarch64)

### Known Issues

1. **PortAudio ALSA assertion crash**: The project already documents this in `documents/docs/guide/异常汇总.md` (line 335-513), specifically the `PaAlsaStreamComponent_BeginPolling` crash. This is more common on ARM/RPi due to:
   - Older PortAudio versions in distro repos
   - ALSA configuration issues with USB audio devices on RPi
   - Missing or misconfigured audio device drivers

2. **sounddevice finding PortAudio**: The Python `sounddevice` package uses `ctypes` to load `libportaudio.so.2`. On ARM systems, the library path may differ:
   - x86_64: `/usr/lib/x86_64-linux-gnu/libportaudio.so.2`
   - aarch64: `/usr/lib/aarch64-linux-gnu/libportaudio.so.2`
   - The `sounddevice` package handles this via `ctypes.util.find_library("portaudio")` which works on both architectures.

3. **Performance on RPi**: PortAudio on Raspberry Pi (especially Pi 3/Zero) can experience buffer underruns due to limited CPU. Recommended mitigations:
   - Use larger buffer sizes (the project uses Opus frames which helps)
   - Ensure PulseAudio/PipeWire is running as intermediary (avoids direct ALSA hardware access issues)

4. **USB audio devices**: On RPi, the built-in 3.5mm audio output has known quality issues. USB audio devices work better but may need ALSA device index configuration.

5. **No known aarch64-specific compilation issues**: Both `portaudio19-dev` and `sounddevice` (which includes pre-built wheels for Linux aarch64) install cleanly on ARM64. The `sounddevice` PyPI package ships `manylinux` wheels for `aarch64` since version 0.4.4+.

### Bundled Opus on ARM

The project includes a pre-built `libs/libopus/linux/arm64/libopus.so` (from `opus_loader.py` search path at line 35: `/usr/lib/aarch64-linux-gnu/libopus.so.0`), providing a fallback even if `libopus0` is not installed via apt.

---

## Cross-Reference: Existing Code Paths for Audio Discovery

### opus_loader.py (line 32-36) -- Linux opus search paths
```python
candidates = [
    "/usr/lib/libopus.so.0",
    "/usr/lib/x86_64-linux-gnu/libopus.so.0",
    "/usr/lib/aarch64-linux-gnu/libopus.so.0",
    "/usr/local/lib/libopus.so",
]
```
These paths are correct for all target platforms.

### volume_controller.py -- Uses `pactl`, `wpctl`, `amixer` 
The volume controller already has multi-backend support for PulseAudio, PipeWire (wpctl), and ALSA (amixer). This is appropriate for the range of audio servers across versions.

---

## Consolidated Package Matrix

| Package | Ubuntu 20.04 | Ubuntu 22.04 | Ubuntu 24.04 | Ubuntu 25.04 | RPi Bullseye | RPi Bookworm |
|---|---|---|---|---|---|---|
| **portaudio19-dev** | Available | Available | Available | Available | Available | Available |
| **libportaudio2** | Available | Available | Available | Available | Available | Available |
| **libasound2-dev** | Canonical | Canonical | Transitional | Transitional | Canonical | Transitional |
| **libasound-dev** | N/A | N/A | Canonical | Canonical | N/A | Canonical |
| **libopus0** | Available | Available | Available | Available | Available | Available |
| **libopus-dev** | Available | Available | Available | Available | Available | Available |
| **ffmpeg** | Available (4.2) | Available (4.4) | Available (6.1) | Available (7.0+) | Available (4.3) | Available (5.1) |
| **pulseaudio-utils** | Available | Available | Available | Available | Available | Available |
| **pulseaudio** | Default server | Replaced by PipeWire | Replaced | Replaced | Default server | Replaced by PipeWire |
| **pipewire** | N/A | Default server | Default | Default | N/A | Default server |
| **pipewire-pulse** | N/A | Default | Default | Default | N/A | Default |
| **Default Python** | 3.8 | 3.10 | 3.12 | 3.13 | 3.9 | 3.11 |
| **Python 3.10+ native** | No (needs PPA) | Yes | Yes | Yes | No (needs PPA/pyenv) | Yes |
| **build-essential** | Available | Available | Available | Available | Available | Available |

---

## Recommended Install Commands by Version

### Ubuntu 20.04
```bash
# Python 3.10+ required first
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt update
sudo apt install python3.10 python3.10-venv python3.10-dev

# Audio deps
sudo apt-get install -y \
    portaudio19-dev libportaudio2 \
    ffmpeg libopus0 libopus-dev \
    libasound2-dev \
    pulseaudio-utils \
    build-essential
```

### Ubuntu 22.04
```bash
sudo apt-get install -y \
    portaudio19-dev libportaudio2 \
    ffmpeg libopus0 libopus-dev \
    libasound2-dev \
    pulseaudio-utils \
    build-essential python3-venv python3-pip
# Note: Do NOT install `pulseaudio` daemon -- PipeWire is default
```

### Ubuntu 24.04 / 25.04
```bash
sudo apt-get install -y \
    portaudio19-dev libportaudio2 \
    ffmpeg libopus0 libopus-dev \
    libasound-dev \
    pulseaudio-utils \
    build-essential python3-venv python3-pip
# Note: Use libasound-dev (not libasound2-dev) as canonical name
# libasound2-dev still works as transitional
```

### Raspberry Pi OS Bookworm (Desktop)
```bash
sudo apt-get install -y \
    portaudio19-dev libportaudio2 \
    ffmpeg libopus0 libopus-dev \
    libasound-dev \
    pulseaudio-utils \
    build-essential python3-venv python3-pip
# PipeWire already running, pactl works via pipewire-pulse
```

### Raspberry Pi OS Bookworm (Lite / Headless)
```bash
# Need audio server for non-ALSA-direct access
sudo apt-get install -y \
    pipewire pipewire-pulse wireplumber \
    portaudio19-dev libportaudio2 \
    ffmpeg libopus0 libopus-dev \
    libasound-dev \
    pulseaudio-utils \
    build-essential python3-venv python3-pip
```

### Raspberry Pi OS Bullseye
```bash
sudo apt-get install -y \
    portaudio19-dev libportaudio2 \
    ffmpeg libopus0 libopus-dev \
    libasound2-dev \
    pulseaudio-utils \
    build-essential python3-venv python3-pip
# Python 3.9 is system default; need pyenv/deadsnakes for 3.10+
```

---

## Caveats / Not Found

1. **Ubuntu 25.04 package specifics**: Ubuntu 25.04 (Plucky Puffin) released April 2025. Package names confirmed consistent with 24.04 Noble conventions. However, as a non-LTS release, long-term support is limited (9 months).

2. **libasound2-dev transitional package longevity**: It is unclear exactly when Debian/Ubuntu will drop the `libasound2-dev` transitional package. For maximum compatibility, an install script should try `libasound2-dev` first and fall back to `libasound-dev`, or simply use `libasound2-dev` which still resolves everywhere today.

3. **RPi OS Bookworm Lite audio server**: The exact pre-installed state on Lite varies by image date. Some later Lite images may include minimal PipeWire. The safest approach is to explicitly install the audio server packages.

4. **Python version inconsistency in project docs**: README.md says "3.9-3.12" but 系统依赖安装.md says ">= 3.10". This should be unified.

5. **sounddevice ARM wheel availability**: Confirmed `sounddevice >= 0.4.4` includes `manylinux_2_17_aarch64` wheels on PyPI. No source compilation needed on ARM64 for recent versions.
