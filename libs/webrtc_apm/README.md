# WebRTC Audio Processing Python Wrapper

Python ctypes bindings for WebRTC Audio Processing Module, providing echo cancellation, noise suppression, automatic gain control, and other audio processing features.

## Features

- **Echo Cancellation (AEC)**: Removes acoustic echo from audio signals
- **Noise Suppression**: Reduces background noise 
- **Automatic Gain Control (AGC)**: Maintains consistent audio levels
- **High-pass Filter**: Removes low-frequency noise
- **Transient Suppression**: Reduces keyboard clicks and other transient sounds
- **Platform Support**: Linux, macOS, and Windows with automatic library loading

## Installation

The wrapper automatically detects your platform and loads the appropriate native library:

- **Linux**: `linux/{arch}/libwebrtc_apm.so`
- **macOS**: `macos/{arch}/libwebrtc_apm.dylib` 
- **Windows**: `windows/{arch}/libwebrtc_apm.dll`

Supported architectures: `x64`, `arm64`, `x86`

## Quick Start

```python
from webrtc_apm import WebRTCAudioProcessing, create_default_config
import ctypes
import numpy as np

# Initialize audio processing
apm = WebRTCAudioProcessing()

# Configure with echo cancellation and noise suppression
config = create_default_config()
config.echo.enabled = True
config.noise_suppress.enabled = True
config.high_pass.enabled = True

# Apply configuration
apm.apply_config(config)

# Create stream configurations for 16kHz mono audio
sample_rate = 16000
num_channels = 1
capture_config = apm.create_stream_config(sample_rate, num_channels)
render_config = apm.create_stream_config(sample_rate, num_channels)

# Set echo delay
apm.set_stream_delay_ms(50)

# Process audio frames
frame_size = 160  # 10ms at 16kHz
capture_audio = np.random.randint(-1000, 1000, frame_size, dtype=np.int16)
render_audio = np.random.randint(-500, 500, frame_size, dtype=np.int16)

# Convert to ctypes arrays
capture_buffer = (ctypes.c_short * frame_size)(*capture_audio)
render_buffer = (ctypes.c_short * frame_size)(*render_audio)
processed_capture = (ctypes.c_short * frame_size)()
processed_render = (ctypes.c_short * frame_size)()

# Process render stream (echo reference)
apm.process_reverse_stream(render_buffer, render_config, render_config, processed_render)

# Process capture stream (apply processing)
apm.process_stream(capture_buffer, capture_config, capture_config, processed_capture)

# Clean up
apm.destroy_stream_config(capture_config)
apm.destroy_stream_config(render_config)
```

## Configuration Options

### Echo Cancellation
```python
config.echo.enabled = True
config.echo.mobile_mode = False  # Use full AEC (not mobile version)
config.echo.enforce_high_pass_filtering = True
```

### Noise Suppression
```python
config.noise_suppress.enabled = True
config.noise_suppress.noise_level = 2  # 0=Low, 1=Moderate, 2=High, 3=VeryHigh
```

### Automatic Gain Control (AGC1)
```python
config.gain_control1.enabled = True
config.gain_control1.controller_mode = 0  # 0=AdaptiveAnalog, 1=AdaptiveDigital, 2=FixedDigital
config.gain_control1.target_level_dbfs = 3
config.gain_control1.compression_gain_db = 9
config.gain_control1.enable_limiter = True
```

### High-pass Filter
```python
config.high_pass.enabled = True
config.high_pass.apply_in_full_band = True
```

## API Reference

### Classes

#### `WebRTCAudioProcessing`
Main audio processing class.

**Methods:**
- `create_stream_config(sample_rate, num_channels)` - Create stream configuration
- `destroy_stream_config(config_handle)` - Destroy stream configuration
- `apply_config(config)` - Apply processing configuration
- `process_stream(src, src_config, dest_config, dest)` - Process capture audio
- `process_reverse_stream(src, src_config, dest_config, dest)` - Process render audio
- `set_stream_delay_ms(delay_ms)` - Set echo delay in milliseconds

#### `Config`
Configuration structure with all processing options.

### Functions

#### `create_default_config()`
Returns a `Config` object with sensible default values.

### Enums

- `DownmixMethod`: How to convert multi-channel to mono
- `NoiseSuppressionLevel`: Noise suppression intensity  
- `GainController1Mode`: AGC operating mode
- `ClippingPredictorMode`: Clipping prediction algorithm

## Examples

See `example.py` for comprehensive usage examples including:
- Basic echo cancellation and noise suppression
- AGC configuration
- Full processing pipeline setup
- Audio frame processing loop

## Audio Format Requirements

- **Sample Rate**: 8000, 16000, 32000, or 48000 Hz
- **Channels**: 1 (mono) or 2 (stereo)
- **Sample Format**: 16-bit signed integer (int16)
- **Frame Size**: 10ms worth of samples (e.g., 160 samples at 16kHz)

## Error Handling

All processing functions return status codes:
- `0`: Success
- Non-zero: Error occurred

```python
result = apm.process_stream(src, src_config, dest_config, dest)
if result != 0:
    print(f"Processing failed with code: {result}")
```

## Performance Notes

- Process audio in 10ms frames for optimal performance
- Reuse stream configurations when possible
- Call `process_reverse_stream()` before `process_stream()` for best echo cancellation
- Set appropriate stream delay based on your audio system latency

## Platform-Specific Notes

### Linux
- Requires the shared library `libwebrtc_apm.so`
- Works on x64 and ARM64 architectures

### macOS  
- Uses dynamic library `libwebrtc_apm.dylib`
- Supports both Intel (x64) and Apple Silicon (arm64)

### Windows
- Requires `libwebrtc_apm.dll`
- Supports x64 and x86 architectures
- May need Visual C++ Redistributable

## Troubleshooting

**Library not found**: Ensure the native library is in the correct platform subdirectory.

**Processing errors**: Check that audio format matches stream configuration (sample rate, channels).

**Poor echo cancellation**: Verify render stream is processed before capture stream and stream delay is set correctly.

**High CPU usage**: Use 10ms frames and appropriate sample rates (16kHz recommended for voice).