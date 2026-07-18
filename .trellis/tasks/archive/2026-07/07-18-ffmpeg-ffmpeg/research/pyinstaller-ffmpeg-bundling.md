# Research: PyInstaller FFmpeg bundling

- **Query**: How py-xiaozhi packs and resolves bundled ffmpeg/ffprobe under PyInstaller onedir
- **Scope**: internal (project pack paths + subprocess notes)
- **Date**: 2026-07-18

## Findings

### Datas already include `libs`

`py-xiaozhi.spec` Analysis:

```python
datas=[('models', 'models'), ('scripts', 'scripts'), ('src', 'src'), ('libs', 'libs'), ('assets', 'assets')],
```

Anything placed at build time under `libs/ffmpeg/<plat>/<arch>/` is copied into the onedir tree as `libs/...` and is available at runtime under the app root. No extra PyInstaller `binaries=` entry is required for plain data-layout executables if they are only launched via absolute path (not imported as extension modules).

### Runtime root: `get_app_root()` → `_MEIPASS`

From `src/utils/resource_finder.py`:

- Frozen (`sys.frozen`): `Path(sys._MEIPASS)` (PyInstaller onedir extract/root).
- Dev: repo root (three levels above `resource_finder.py`).

`get_ffmpeg_path()` / `get_ffprobe_path()`:

1. Prefer `get_app_root() / "libs" / "ffmpeg" / <plat> / <arch> / ffmpeg[.exe]|ffprobe[.exe]`
2. Fallback: `shutil.which(...)` / bare name on PATH

Plat/arch mapping used by finder: `mac`/`win`/`linux` × `arm64`/`x64` (and related). Keep CI inject paths aligned with that layout.

### Executables need `+x` (Unix)

PyInstaller `datas` copy does not guarantee execute bits survive all archive/CI steps. After download/extract and after pack smoke:

```bash
chmod +x libs/ffmpeg/mac/arm64/ffmpeg libs/ffmpeg/mac/arm64/ffprobe
chmod +x libs/ffmpeg/linux/*/ffmpeg libs/ffmpeg/linux/*/ffprobe
```

Windows uses `.exe`; no `+x`.

### Windows: `CREATE_NO_WINDOW` already used

`src/audio_codecs/music_decoder.py` and `src/utils/activation_announcer.py` pass:

```python
{"creationflags": subprocess.CREATE_NO_WINDOW} if sys.platform == "win32" else {}
```

(or set `creationflags` on the Popen kwargs). Prevents console flash when spawning ffmpeg/ffprobe from a windowed (`console=False`) app. Keep this on any new subprocess call sites.

### Shared builds: DLLs same directory as `ffmpeg.exe`

If Windows (or Linux shared) builds are used:

- Copy **all** required DLLs / `.so` next to `ffmpeg.exe` / `ffmpeg` in `libs/ffmpeg/<plat>/<arch>/`.
- Do not rely on system PATH for those libs when resolving via absolute path to the bundled exe (Windows loads DLLs from the executable’s directory by default).
- Static BtbN/johnvansickle-style single binaries avoid this class of failure.

### macOS: Gatekeeper / quarantine on downloaded binaries

Binaries fetched in CI or on a developer machine often get `com.apple.quarantine`. Nested unsigned tools may fail to exec or prompt.

Mitigation at inject time (local/CI script):

```bash
xattr -cr libs/ffmpeg/mac/arm64
```

Outer app signing/notarization of nested ffmpeg is out of scope for this task; still clear quarantine on the injected binaries before packaging when possible.

### UPX note

`py-xiaozhi.spec` has `upx=True` on EXE/COLLECT. UPX on already-packed static ffmpeg is unnecessary and can break some binaries. Prefer excluding `libs/ffmpeg/**` from UPX if pack step compresses collected files (or inject after UPX-sensitive steps). Verify with isolated `-version` after the full package build.

### Smoke after pack

From a clean environment (no brew/system ffmpeg on PATH):

```bash
# conceptual — point at packaged tree under _MEIPASS / onedir
env -i PATH=/usr/bin:/bin "$PACKAGED_ROOT/libs/ffmpeg/$PLAT/$ARCH/ffmpeg" -version
```

App-level: run music decode path and confirm `get_ffmpeg_path()` returns the bundled path under `_MEIPASS`.

## Related project files

| File | Role |
|---|---|
| `py-xiaozhi.spec` | `datas` includes `libs` |
| `src/utils/resource_finder.py` | `_MEIPASS` + bundled path resolution |
| `src/audio_codecs/music_decoder.py` | ffmpeg/ffprobe subprocess + `CREATE_NO_WINDOW` |
| `src/utils/activation_announcer.py` | ffmpeg decode (PRD: replace with WAV) |
| `.github/workflows/build.yml` | current inject step (to be replaced by portable downloads) |

## Caveats

- `datas` ships files as data; they are not registered as PyInstaller “binaries” for PATH injection — resolution must stay absolute via `get_ffmpeg_path()`.
- Do not put only `ffmpeg` on PATH inside the frozen app without also shipping sibling DLLs for shared builds.
- Confirm both `ffmpeg` and `ffprobe` exist for every platform matrix cell.
