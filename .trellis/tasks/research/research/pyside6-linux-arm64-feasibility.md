# Research: PySide6 Linux arm64 (aarch64) Availability & CI Feasibility

- **Query**: PySide6 availability for Linux arm64 via pip/conda, GitHub Actions ARM64 runners, and CI packaging feasibility
- **Scope**: external
- **Date**: 2026-05-15

## Findings

### 1. PyPI: PySide6 aarch64 Wheels

**YES -- PySide6 has official aarch64 Linux wheels on PyPI.**

| Version Range | Wheel Tag | Min glibc | Min Ubuntu |
|---|---|---|---|
| 6.5.3 - 6.8.0.2 | `manylinux_2_31_aarch64` | glibc 2.31 | Ubuntu 20.04 |
| 6.8.1 - 6.11.1 (latest) | `manylinux_2_39_aarch64` | glibc 2.39 | Ubuntu 24.04 |

First version with aarch64: **6.5.3** (cp37-abi3)
Latest version with aarch64: **6.11.1** (cp310-abi3)

Key sub-packages also have aarch64 wheels:
- `PySide6-Essentials` -- aarch64 wheel available (6.11.1)
- `shiboken6` -- aarch64 wheel available (6.11.1)

**Important glibc constraint**: Starting from PySide6 6.8.1, the aarch64 wheel requires `manylinux_2_39` which means glibc 2.39+. This is only available on Ubuntu 24.04+ or equivalent. If running on Ubuntu 22.04 arm64, you are limited to PySide6 <= 6.8.0.2.

### 2. conda-forge: PySide6 for linux-aarch64

**YES -- conda-forge has PySide6 for linux-aarch64.**

- 302 linux-aarch64 files available on conda-forge
- Support goes back to at least version 6.4.0
- Latest version: 6.11.1
- conda-forge builds its own packages so glibc constraints may differ from PyPI

### 3. Other Installation Methods

#### Building from Source
- Qt for Python (PySide6) can be built from source on any Linux aarch64 system
- Requires Qt6 libraries, CMake, and a C++ compiler
- Build time is significant (1-2 hours+ on ARM hardware)
- Not practical for CI; use pre-built wheels

#### System Packages
- Some Linux distributions package PySide6 in their repositories:
  - Arch Linux ARM: `python-pyside6` available
  - Fedora: `python3-pyside6` available for aarch64
  - Ubuntu: Not available as a system package (use pip)

### 4. GitHub Actions ARM64 Ubuntu Runners

**YES -- GitHub Actions has native ARM64 Ubuntu runners.**

#### Runner Labels
| Label | OS | Status |
|---|---|---|
| `ubuntu-24.04-arm` | Ubuntu 24.04 ARM64 | Available (GA) |
| `ubuntu-22.04-arm` | Ubuntu 22.04 ARM64 | Available (GA) |

#### Availability & Pricing
- **Public repositories**: FREE (public preview since Jan 2025, per [GitHub blog changelog](https://github.blog/changelog/2025-01-16-linux-arm64-hosted-runners-now-available-for-free-in-public-repositories-public-preview/))
- **Private repositories**: Requires "Larger Runners" plan (paid), billed at the same rate as Linux 2-core standard runners
- These runners are now maintained directly by GitHub (as of May 2026, per [actions/runner-images#14100](https://github.com/actions/runner-images/issues/14100))

#### Known Issues
- During the GitHub takeover transition (May 2026), images may not receive updates temporarily
- Docker may be missing on some ARM64 runner image versions ([#14051](https://github.com/actions/runner-images/issues/14051)) -- relevant if using Docker-based builds
- No `-latest` alias yet for ARM runners (requested in [#13885](https://github.com/actions/runner-images/issues/13885)); must use explicit `ubuntu-24.04-arm`

### 5. Other Key Dependencies -- aarch64 Availability

All critical project dependencies have aarch64 wheels on PyPI:

| Package | aarch64 Available | Notes |
|---|---|---|
| PySide6 >= 6.6.0 | Yes | manylinux_2_31 or _2_39 |
| PyInstaller | Yes | `manylinux2014_aarch64` wheel |
| sherpa-onnx | Yes | Per-Python-version wheels (cp310-cp314) |
| sherpa-onnx-core | Yes | `manylinux2014_aarch64` |
| numpy | Yes | Standard support |
| opencv-python-headless | Yes | Standard support |
| opuslib | N/A | Pure Python (sdist), needs `libopus` system lib |
| qasync | N/A | Pure Python |

### 6. Recommended CI Configuration

For `ubuntu-24.04-arm` runner with PySide6:
- Use **PySide6 >= 6.8.1** (latest wheels target manylinux_2_39, matching Ubuntu 24.04's glibc 2.39)
- Or pin **PySide6 == 6.8.0.2** if needing Ubuntu 22.04 compatibility
- Install system dependencies: `sudo apt-get install libgl1 libegl1 libxkbcommon0 libopus0`
- PyInstaller packaging will work natively -- no QEMU/cross-compilation needed

#### Alternative: QEMU Cross-Architecture (if native runner unavailable)
- Use `docker/setup-qemu-action` + Docker buildx on a standard x86_64 runner
- Much slower (10-50x) due to CPU emulation
- The `uraimo/run-on-arch-action` GitHub Action wraps QEMU for simpler setup
- Not recommended when native runners are available

## Caveats / Risks

1. **glibc version pinch**: The project requires `PySide6>=6.6.0` but the latest wheels need glibc 2.39. On Ubuntu 24.04 this is fine; on Ubuntu 22.04 arm64, pip would auto-resolve to an older compatible version (6.8.0.2 or below), but this may not always work cleanly.

2. **Runner image stability**: GitHub just took over ARM64 runner images from Arm Ltd (May 2026). During transition, updates may be delayed. Docker availability has been reported as inconsistent on ARM64 images.

3. **Private repo cost**: ARM64 runners are free only for public repos. For private repos, they require the "Larger Runners" plan.

4. **No `-latest` alias**: Must pin to `ubuntu-24.04-arm` explicitly. No `ubuntu-arm-latest` alias exists yet.

5. **opuslib needs system library**: `opuslib` is pure Python but requires `libopus-dev`/`libopus0` to be installed via apt on the runner.
