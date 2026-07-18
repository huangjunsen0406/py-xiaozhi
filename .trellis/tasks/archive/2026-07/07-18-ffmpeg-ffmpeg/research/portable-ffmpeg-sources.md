# Research: Portable FFmpeg sources for CI bundling

- **Query**: Portable / redistributable FFmpeg builds suitable for CI injection into `libs/ffmpeg/<plat>/<arch>/` (not brew/apt/choco dynamic copies)
- **Scope**: mixed (external sources + project path layout)
- **Date**: 2026-07-18

## Problem

Homebrew, apt, and Chocolatey FFmpeg packages are **dynamically linked** against distro/Homebrew library trees:

- macOS Homebrew: `ffmpeg` depends on `/opt/homebrew/opt/...` dylibs (or `/usr/local/opt/...` on Intel). Copying `$(which ffmpeg)` into the app fails on machines without those libraries.
- Linux apt: depends on distro `.so` versions; may pull a large transitive set and break on other distros/versions.
- Windows Chocolatey: often ships real binaries under `tools/ffmpeg/bin`, but CI currently can still fall back to a shim; dependency set is not guaranteed portable.

`cp $(which ffmpeg)` into `libs/ffmpeg/...` therefore works on the builder and fails on clean user machines. py-xiaozhi already resolves bundled binaries first:

- Path layout: `libs/ffmpeg/<plat>/<arch>/ffmpeg[.exe]` and `ffprobe[.exe]`
  - plat: `mac` | `win` | `linux`
  - arch: `arm64` | `x64`
- Code: `src/utils/resource_finder.py` → `get_ffmpeg_path()` / `get_ffprobe_path()` prefer `get_app_root() / "libs" / "ffmpeg" / ...`, then PATH.
- PyInstaller: `py-xiaozhi.spec` already includes `('libs', 'libs')` under `datas`.

Need **redistributable** (static or self-contained shared) builds downloaded per platform in CI / local pack scripts.

## Findings

### Files Found (project)

| File Path | Description |
|---|---|
| `src/utils/resource_finder.py` | `get_app_root()`, `get_ffmpeg_path()`, `get_ffprobe_path()`; frozen uses `sys._MEIPASS` |
| `src/audio_codecs/music_decoder.py` | Primary consumer; Windows `CREATE_NO_WINDOW` |
| `src/utils/activation_announcer.py` | Currently also spawns ffmpeg (PRD: move to WAV) |
| `.github/workflows/build.yml` | Current Bundle FFmpeg step: brew/apt/choco + `cp` |
| `py-xiaozhi.spec` | `datas` includes `('libs', 'libs')` |
| `LICENSE` / `pyproject.toml` | MIT |

### Options compared

#### 1. BtbN/FFmpeg-Builds (GitHub releases)

- **URL**: https://github.com/BtbN/FFmpeg-Builds/releases
- **Platforms**: Windows (win64), Linux (linux64, linuxarm64). **No macOS.**
- **License variants**: `gpl` and `lgpl` (and gpl/lgpl with shared).
- **Linking variants**: `shared` (ffmpeg + many DLLs/SOs) and non-shared/static-style essentials.
- **Asset name patterns** (latest rolling master builds; also versioned tags):
  - Windows: `ffmpeg-master-latest-win64-gpl-shared.zip`, `ffmpeg-master-latest-win64-lgpl-shared.zip`, `...-win64-gpl.zip` (static-ish single binaries)
  - Linux x64: `ffmpeg-master-latest-linux64-gpl-shared.tar.xz`, `...-linux64-lgpl.tar.xz`, etc.
  - Linux arm64: `ffmpeg-master-latest-linuxarm64-gpl.tar.xz`, `...-linuxarm64-lgpl-shared.tar.xz`, etc.
- **Layout after extract**: usually `bin/ffmpeg`, `bin/ffprobe` (and `bin/*.dll` on Windows shared).
- **Notes**: Widely used for CI redistributable bundling. Prefer **lgpl** when app is MIT and you want fewer copyleft obligations; use **gpl** only if you accept GPL redistribution implications. Shared builds need adjacent DLLs/SOs next to the exe (or `LD_LIBRARY_PATH` / rpath — same-dir is simplest on Windows).

#### 2. gyan.dev Windows builds

- **URL**: https://www.gyan.dev/ffmpeg/builds/
- **Platforms**: Windows x64 primarily.
- **Variants**: “essentials”, “full”, git/release builds; often shared with DLLs in `bin/`.
- **Notes**: Popular Windows-only alternative to BtbN. Essentials is smaller and enough for decode-to-PCM + ffprobe duration. Same rule: copy `ffmpeg.exe`, `ffprobe.exe`, and any sibling DLLs if present.

#### 3. evermeet.cx macOS builds

- **URL**: https://evermeet.cx/ffmpeg/
- **Platforms**: historically **macOS x86_64** static-ish single binaries (`ffmpeg`, `ffprobe`).
- **arm64**: not a reliable primary source for Apple Silicon; do not assume arm64 coverage.
- **Notes**: Fine for Intel Mac historical packaging; **not sufficient alone** for current py-xiaozhi CI which targets mac arm64.

#### 4. osxexperts.net / other mac arm64 builds

- Community static builds for **macOS arm64** (and sometimes universal) appear on sites such as osxexperts.net and various GitHub mirrors.
- **Caveats**:
  - Availability and update cadence vary; verify HTTPS URL and checksum when pinning.
  - Not “official FFmpeg project” binaries; treat as third-party redistributable builds.
  - Always verify with `otool -L` that there is no `/opt/homebrew` or `/usr/local/Cellar` dependency.
- **Alternative for mac**: extract the platform binary shipped by **imageio-ffmpeg** (see below) if a trusted static arm64 URL is not pinned yet.

#### 5. johnvansickle.com Linux static

- **URL**: https://johnvansickle.com/ffmpeg/
- **Platforms**: Linux **amd64** and **arm64** static builds (single `ffmpeg` / `ffprobe` binaries).
- **Notes**: Long-standing static Linux packaging. Good fallback or primary for linux x64/arm64 when BtbN shared is undesirable. Static preferred for “no missing `.so`” smoke tests via `ldd`.

#### 6. imageio-ffmpeg (Python wheel)

- **Package**: `imageio-ffmpeg` on PyPI.
- **Behavior**: ships a platform-specific ffmpeg binary inside the wheel; Python API returns path via `imageio_ffmpeg.get_ffmpeg_exe()`.
- **Strengths**: Easy local/dev acquisition; often works for decode; CI can `pip download` / install and copy the embedded binary into `libs/ffmpeg/...`.
- **Limitations**:
  - Historically limited architecture matrix (not all arm/OS combos always present).
  - May ship **ffmpeg only** (not always ffprobe) — project needs **both**.
  - Version and license of the embedded build are package-defined; still verify linkage and license.
- **Use case**: Practical **mac arm64** bootstrap when a dedicated static URL is not yet chosen; not ideal as the sole multi-platform strategy.

#### 7. static-ffmpeg (PyPI)

- **Package**: `static-ffmpeg` on PyPI.
- **Behavior**: downloads/caches static ffmpeg/ffprobe for the host platform; exposes paths for subprocess use.
- **Notes**: Convenient for Python apps that shell out; for **bundled app** shipping, still extract/copy into `libs/ffmpeg/<plat>/<arch>/` so PyInstaller `datas` and `get_ffmpeg_path()` work without depending on the package at runtime. Confirm supported platforms (esp. mac arm64) before relying in CI.

### Comparison summary

| Source | win x64 | linux x64 | linux arm64 | mac x64 | mac arm64 | static/shared | LGPL option |
|---|---|---|---|---|---|---|---|
| BtbN/FFmpeg-Builds | yes | yes | yes | no | no | both | yes |
| gyan.dev | yes | no | no | no | no | mostly shared | check build |
| evermeet.cx | no | no | no | yes (hist.) | weak/no | static-ish | check |
| osxexperts / community mac | no | no | no | varies | yes (varies) | often static | check |
| johnvansickle | no | yes | yes | no | no | static | check (often GPL-enabled) |
| imageio-ffmpeg | yes* | yes* | limited* | yes* | yes* | embedded | package-defined |
| static-ffmpeg PyPI | yes* | yes* | check | check | check | static | package-defined |

\*Depends on current wheel/release matrix — pin and verify in CI.

## Recommended strategy (PRIMARY)

Per-platform download of redistributable builds into `libs/ffmpeg/<plat>/<arch>/` (gitignored; CI + local pack script inject).

| Platform | Source | Notes |
|---|---|---|
| **macos arm64** | Prefer a redistributable **arm64** build: known community static URL (e.g. osxexperts-class build) **or** extract from `imageio-ffmpeg` / `static-ffmpeg` if verified. | **Never** `cp` Homebrew. After place: `chmod +x`; clear quarantine if needed (`xattr -cr`). `otool -L` must not reference `/opt/homebrew`. |
| **windows x64** | **BtbN** `win64` **lgpl** (or gpl if accepted) essentials/static **or** gyan essentials | Copy `ffmpeg.exe`, `ffprobe.exe`; if **shared**, copy **all adjacent DLLs** into the same directory as the exes. |
| **linux x64** | **BtbN** `linux64` static/lgpl **or** johnvansickle amd64 | Prefer static for clean `ldd`. Shared: ship `.so` next to binary or set rpath carefully. |
| **linux arm64** | **BtbN** `linuxarm64` **or** johnvansickle arm64 | Same as linux x64. |

Prefer **BtbN lgpl** on Windows/Linux when available to reduce GPL coupling with MIT app; document if gpl is chosen for codec coverage.

Target layout example:

```text
libs/ffmpeg/mac/arm64/ffmpeg
libs/ffmpeg/mac/arm64/ffprobe
libs/ffmpeg/win/x64/ffmpeg.exe
libs/ffmpeg/win/x64/ffprobe.exe
libs/ffmpeg/win/x64/*.dll          # if shared
libs/ffmpeg/linux/x64/ffmpeg
libs/ffmpeg/linux/x64/ffprobe
libs/ffmpeg/linux/arm64/ffmpeg
libs/ffmpeg/linux/arm64/ffprobe
```

### Example bash outline (GitHub Actions / `scripts/bundle_ffmpeg.sh`)

```bash
#!/usr/bin/env bash
set -euo pipefail

# Resolve PLAT/ARCH → DEST=libs/ffmpeg/$PLAT/$ARCH
# Download pinned release asset (curl -L), verify checksum if available
# Extract only ffmpeg + ffprobe (+ Windows DLLs if shared)
# chmod +x on Unix
# Smoke: env -i PATH=/usr/bin:/bin "$DEST/ffmpeg" -version  (adapt PATH on Windows)

DEST="libs/ffmpeg/${PLAT}/${ARCH}"
mkdir -p "$DEST"

case "${RUNNER_OS:-$(uname -s)}" in
  Windows*|MINGW*|MSYS*)
    # Example: BtbN win64 lgpl shared or static
    # curl -L -o /tmp/ffmpeg.zip "$BTBN_WIN64_URL"
    # unzip -j /tmp/ffmpeg.zip '*/bin/ffmpeg.exe' '*/bin/ffprobe.exe' '*/bin/*.dll' -d "$DEST"
    ;;
  Linux)
    # BtbN linux64/linuxarm64 or johnvansickle
    # tar -xJf ... --strip-components=... -C "$DEST" ffmpeg ffprobe
    chmod +x "$DEST/ffmpeg" "$DEST/ffprobe"
    ;;
  Darwin*|macOS)
    # arm64 redistributable static (NOT brew)
    # curl -L -o "$DEST/ffmpeg" "$MAC_ARM64_FFMPEG_URL"
    # curl -L -o "$DEST/ffprobe" "$MAC_ARM64_FFPROBE_URL"
    chmod +x "$DEST/ffmpeg" "$DEST/ffprobe"
    xattr -cr "$DEST" 2>/dev/null || true
    ;;
esac

# Verification (fail CI on non-zero)
if [[ -f "$DEST/ffmpeg.exe" ]]; then
  "$DEST/ffmpeg.exe" -version
else
  env -i PATH=/usr/bin:/bin HOME="$HOME" "$DEST/ffmpeg" -version
fi
```

Pin **exact release URLs or git tags + asset names** in the script (not free-floating `latest` without recording the resolved version in CI logs).

## Verification

```bash
# Isolated run — must not rely on user PATH / Homebrew
env -i PATH=/usr/bin:/bin "$DEST/ffmpeg" -version
env -i PATH=/usr/bin:/bin "$DEST/ffprobe" -version

# mac: must not reference Homebrew cellar
otool -L "$DEST/ffmpeg"
# expect: only system dylds (e.g. /usr/lib/libSystem.B.dylib) or self-contained @rpath — NOT /opt/homebrew

# linux: static preferred; shared must not need missing non-system libs
ldd "$DEST/ffmpeg" || true   # static often prints "not a dynamic executable"

# windows: run -version; ensure DLLs sit beside ffmpeg.exe if shared
```

CI should fail the job if `-version` exits non-zero under isolated PATH.

## License

- **py-xiaozhi** is **MIT** (`LICENSE`, `pyproject.toml`).
- FFmpeg itself: core under LGPL; many builds enable GPL components (libx264, etc.) → whole binary often treated as **GPL** when those are linked.
- **BtbN** publishes both **`lgpl`** and **`gpl`** asset variants — prefer **lgpl** for MIT app redistribution when codec set is sufficient for music decode (PCM output from common formats).
- Bundling **GPL** ffmpeg into a distributed app has implications (source offer / GPL obligations for the combined work depending on linking and distribution model). Document choice in release notes / third-party notices if GPL builds are used.
- Always ship attribution (FFmpeg license text) with the app when redistributing binaries.

## Caveats / Not Found

- No single official “FFmpeg project” multi-OS static CDN covering mac arm64 + win + linux; community builds are the norm.
- macOS arm64 remains the weakest “official” story; must pin a verified redistributable source and re-check `otool -L` after every bump.
- imageio-ffmpeg / static-ffmpeg convenience packages may omit ffprobe or lag arch support — always assert both binaries exist after extract.
- Code signing / notarization of nested ffmpeg on mac is **out of scope** per task PRD; Gatekeeper may still prompt or block unsigned downloaded binaries until `xattr` quarantine is cleared or the outer app is signed.
