# system_loopback

Cross-platform lightweight system audio loopback capture library for `py-xiaozhi` system-level AEC (far-end reference).

## Architecture

All three platforms expose one identical C ABI (`native/system_loopback.h`) backed by a lock-free SPSC float32 ring buffer:

| Platform | Implementation | Requirement |
|---|---|---|
| **macOS** | `native/macos_tap.m` — Core Audio Process Tap (`CATapDescription` + private Aggregate Device) | macOS 14.2+ & System Audio Recording permission (no BlackHole required) |
| **Windows** | `native/windows_wasapi.cpp` — WASAPI Shared-Mode Loopback + 10ms silence keepalive | Windows 10+ (standard Windows SDK) |
| **Linux** | `native/linux_pulse.c` — Async `pa_threaded_mainloop` recording `@DEFAULT_MONITOR@` via `dlopen("libpulse.so.0")` | PipeWire (`pipewire-pulse`) or PulseAudio |

## Building

```bash
# Current host architecture
python scripts/build_system_loopback.py

# macOS: build both arm64 and x64 dylibs
python scripts/build_system_loopback.py --arch all
```
