#!/usr/bin/env bash
# Bundle redistributable ffmpeg + ffprobe into libs/ffmpeg/<plat>/<arch>/
# Never copy Homebrew/apt/choco dynamic-linked binaries as the only strategy.
#
# Usage:
#   ./scripts/bundle_ffmpeg.sh              # auto-detect host platform
#   ./scripts/bundle_ffmpeg.sh mac arm64
#   ./scripts/bundle_ffmpeg.sh win x64
#   ./scripts/bundle_ffmpeg.sh linux x64
#   ./scripts/bundle_ffmpeg.sh linux arm64
#
# Env:
#   FFMPEG_BTBN_TAG   default: latest (BtbN rolling asset names use master-latest)
#   SKIP_SMOKE=1      skip isolated -version check

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# Prefer project venv / uv so `static_ffmpeg` installed via uv pip is visible
resolve_python() {
  if [[ -n "${PYTHON:-}" ]] && command -v "$PYTHON" >/dev/null 2>&1; then
    echo "$PYTHON"
    return
  fi
  if [[ -x "$ROOT/.venv/bin/python" ]]; then
    echo "$ROOT/.venv/bin/python"
    return
  fi
  if [[ -x "$ROOT/.venv/Scripts/python.exe" ]]; then
    echo "$ROOT/.venv/Scripts/python.exe"
    return
  fi
  if command -v uv >/dev/null 2>&1; then
    # uv run uses project env without requiring shell activation
    echo "uv run --no-sync python"
    return
  fi
  command -v python3 >/dev/null 2>&1 && echo "python3" && return
  command -v python >/dev/null 2>&1 && echo "python" && return
  echo "python3"
}

# shellcheck disable=SC2086
py_run() {
  # Run a python snippet with the resolved interpreter (may be multi-word: uv run ...)
  local code="$1"
  if [[ "${PYTHON_CMD}" == "uv run --no-sync python" ]]; then
    uv run --no-sync python -c "$code"
  else
    "$PYTHON_CMD" -c "$code"
  fi
}

# shellcheck disable=SC2086
py_script() {
  # Run a heredoc/script on stdin
  if [[ "${PYTHON_CMD}" == "uv run --no-sync python" ]]; then
    uv run --no-sync python "$@"
  else
    "$PYTHON_CMD" "$@"
  fi
}

PYTHON_CMD="$(resolve_python)"
echo "    using Python: ${PYTHON_CMD}"

detect_plat_arch() {
  local os arch
  os="$(uname -s)"
  arch="$(uname -m)"
  case "$os" in
    Darwin)
      PLAT="mac"
      case "$arch" in
        arm64|aarch64) ARCH="arm64" ;;
        *) ARCH="x64" ;;
      esac
      ;;
    Linux)
      PLAT="linux"
      case "$arch" in
        aarch64|arm64) ARCH="arm64" ;;
        *) ARCH="x64" ;;
      esac
      ;;
    MINGW*|MSYS*|CYGWIN*|Windows_NT)
      PLAT="win"
      ARCH="x64"
      ;;
    *)
      echo "Unsupported OS: $os" >&2
      exit 1
      ;;
  esac
}

if [[ $# -ge 2 ]]; then
  PLAT="$1"
  ARCH="$2"
elif [[ $# -eq 0 ]]; then
  detect_plat_arch
else
  echo "Usage: $0 [plat arch]" >&2
  exit 1
fi

DEST="libs/ffmpeg/${PLAT}/${ARCH}"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

mkdir -p "$DEST"
# clear previous inject (keep directory)
find "$DEST" -mindepth 1 -maxdepth 1 -exec rm -rf {} +

echo "==> Bundling FFmpeg for ${PLAT}/${ARCH} -> ${DEST}"

BTBN_BASE="https://github.com/BtbN/FFmpeg-Builds/releases/download/latest"

download() {
  local url="$1" out="$2"
  echo "    curl $url"
  curl -fsSL --retry 3 -o "$out" "$url"
}

smoke_unix() {
  local bin="$1"
  chmod +x "$bin"
  if [[ "${SKIP_SMOKE:-0}" == "1" ]]; then
    return 0
  fi
  env -i PATH="/usr/bin:/bin" HOME="${HOME:-/tmp}" "$bin" -version >/dev/null
  echo "    smoke OK: $bin"
}

smoke_win() {
  local bin="$1"
  if [[ "${SKIP_SMOKE:-0}" == "1" ]]; then
    return 0
  fi
  "$bin" -version >/dev/null
  echo "    smoke OK: $bin"
}

check_mac_no_homebrew() {
  local bin="$1"
  if ! command -v otool >/dev/null 2>&1; then
    return 0
  fi
  if otool -L "$bin" | grep -E '/opt/homebrew|/usr/local/Cellar' >/dev/null; then
    echo "ERROR: $bin still links Homebrew paths (not portable)" >&2
    otool -L "$bin" >&2
    exit 1
  fi
}

bundle_btbn_linux() {
  local asset arch_token
  if [[ "$ARCH" == "arm64" ]]; then
    arch_token="linuxarm64"
  else
    arch_token="linux64"
  fi
  # lgpl non-shared: fewer GPL obligations for MIT app; self-contained enough for decode
  asset="ffmpeg-master-latest-${arch_token}-lgpl.tar.xz"
  download "${BTBN_BASE}/${asset}" "$TMP/ffmpeg.tar.xz"
  tar -xJf "$TMP/ffmpeg.tar.xz" -C "$TMP"
  local bin_dir
  bin_dir="$(find "$TMP" -type d -name bin | head -1)"
  if [[ -z "$bin_dir" ]]; then
    echo "ERROR: bin/ not found in BtbN archive" >&2
    exit 1
  fi
  cp "$bin_dir/ffmpeg" "$bin_dir/ffprobe" "$DEST/"
  smoke_unix "$DEST/ffmpeg"
  smoke_unix "$DEST/ffprobe"
}

bundle_btbn_win() {
  local asset="ffmpeg-master-latest-win64-lgpl.zip"
  download "${BTBN_BASE}/${asset}" "$TMP/ffmpeg.zip"
  mkdir -p "$TMP/extract"
  if command -v unzip >/dev/null 2>&1; then
    unzip -q "$TMP/ffmpeg.zip" -d "$TMP/extract"
  else
    py_run "import zipfile; zipfile.ZipFile(r'$TMP/ffmpeg.zip').extractall(r'$TMP/extract')"
  fi
  local bin_dir
  bin_dir="$(find "$TMP/extract" -type d -name bin | head -1)"
  if [[ -z "$bin_dir" ]]; then
    echo "ERROR: bin/ not found in BtbN zip" >&2
    exit 1
  fi
  # static-ish lgpl zip: ffmpeg.exe + ffprobe.exe (no shared DLL set)
  cp "$bin_dir/ffmpeg.exe" "$bin_dir/ffprobe.exe" "$DEST/"
  # if shared build ever used, copy DLLs:
  find "$bin_dir" -maxdepth 1 -name '*.dll' -exec cp {} "$DEST/" \;
  smoke_win "$DEST/ffmpeg.exe"
  smoke_win "$DEST/ffprobe.exe"
}

is_homebrew_path() {
  case "$1" in
    /opt/homebrew/*|/usr/local/Cellar/*|/usr/local/opt/*) return 0 ;;
    *) return 1 ;;
  esac
}

bundle_mac() {
  # Prefer static-ffmpeg embedded binaries; never copy Homebrew.
  # Do NOT use shutil.which after weak add_paths — that picks system brew.
  local ffmpeg_src="" ffprobe_src=""

  if py_run "import static_ffmpeg" 2>/dev/null; then
    # Write paths to a side-channel file. static_ffmpeg may print
    # "Downloading ..." to stdout on cold cache; never eval that stdout.
    local sf_paths="$TMP/sf_paths"
    if py_script - <<PY
from static_ffmpeg.run import get_or_fetch_platform_executables_else_raise

ffmpeg, ffprobe = get_or_fetch_platform_executables_else_raise()
with open(r"$sf_paths", "w", encoding="utf-8") as f:
    f.write(ffmpeg + "\n" + ffprobe + "\n")
PY
    then
      # Read only the two path lines written by Python (ignore any download logs)
      {
        IFS= read -r ffmpeg_src || true
        IFS= read -r ffprobe_src || true
      } <"$sf_paths"
      echo "    static_ffmpeg: ffmpeg=$ffmpeg_src"
      echo "    static_ffmpeg: ffprobe=$ffprobe_src"
    else
      echo "    static_ffmpeg: get_or_fetch failed (will try fallbacks)" >&2
    fi
  fi

  # Fallback: imageio_ffmpeg (often ffmpeg only)
  if [[ -z "$ffmpeg_src" ]] || [[ ! -f "$ffmpeg_src" ]]; then
    if py_run "import imageio_ffmpeg" 2>/dev/null; then
      ffmpeg_src="$(py_run "import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())")"
      echo "    imageio_ffmpeg: ffmpeg=$ffmpeg_src"
    fi
  fi

  if [[ -z "$ffmpeg_src" ]] || [[ ! -f "$ffmpeg_src" ]]; then
    echo "ERROR: No portable mac ffmpeg found." >&2
    echo "  Install into the project env:" >&2
    echo "    uv pip install static-ffmpeg   # or: pip install static-ffmpeg" >&2
    echo "  Do NOT use Homebrew ffmpeg for bundling." >&2
    exit 1
  fi

  if is_homebrew_path "$ffmpeg_src"; then
    echo "ERROR: Refusing to bundle Homebrew ffmpeg: $ffmpeg_src" >&2
    exit 1
  fi

  cp "$ffmpeg_src" "$DEST/ffmpeg"

  if [[ -n "${ffprobe_src:-}" ]] && [[ -f "$ffprobe_src" ]] && ! is_homebrew_path "$ffprobe_src"; then
    cp "$ffprobe_src" "$DEST/ffprobe"
  fi

  # Sibling next to ffmpeg (static_ffmpeg layout / imageio)
  if [[ ! -f "$DEST/ffprobe" ]]; then
    local sibling
    sibling="$(dirname "$ffmpeg_src")/ffprobe"
    if [[ -f "$sibling" ]] && ! is_homebrew_path "$sibling"; then
      cp "$sibling" "$DEST/ffprobe"
    fi
  fi

  if [[ ! -f "$DEST/ffprobe" ]]; then
    echo "ERROR: portable ffprobe not found (install static-ffmpeg for mac bundling)" >&2
    exit 1
  fi

  chmod +x "$DEST/ffmpeg" "$DEST/ffprobe"
  xattr -cr "$DEST" 2>/dev/null || true
  check_mac_no_homebrew "$DEST/ffmpeg"
  check_mac_no_homebrew "$DEST/ffprobe"
  smoke_unix "$DEST/ffmpeg"
  smoke_unix "$DEST/ffprobe"
}

case "$PLAT" in
  linux) bundle_btbn_linux ;;
  win) bundle_btbn_win ;;
  mac) bundle_mac ;;
  *)
    echo "Unknown plat: $PLAT (expected mac|win|linux)" >&2
    exit 1
    ;;
esac

# Final layout guard (fail CI if either binary missing)
if [[ "$PLAT" == "win" ]]; then
  ffmpeg_bin="$DEST/ffmpeg.exe"
  ffprobe_bin="$DEST/ffprobe.exe"
else
  ffmpeg_bin="$DEST/ffmpeg"
  ffprobe_bin="$DEST/ffprobe"
fi
if [[ ! -f "$ffmpeg_bin" ]] || [[ ! -f "$ffprobe_bin" ]]; then
  echo "ERROR: expected both binaries under $DEST" >&2
  ls -la "$DEST" >&2 || true
  exit 1
fi
if [[ "$PLAT" != "win" ]]; then
  chmod +x "$ffmpeg_bin" "$ffprobe_bin"
fi

echo "==> Done. Contents of $DEST:"
ls -lh "$DEST"
