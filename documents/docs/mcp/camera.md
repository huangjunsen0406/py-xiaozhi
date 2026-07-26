# Camera Tools

The camera tool is an intelligent vision recognition MCP tool, providing image capture, visual analysis, and image understanding capabilities.

### Common Use Cases

**Image Recognition and Analysis:**
- "Take a photo and tell me what this is"
- "Take a photo to identify this object"
- "Use the camera to see what's in front of me"
- "See what this thing is"
- "Identify what this is"
- "Help me look at this"
- "Take a photo to analyze this item"

**Scene Understanding:**
- "Take a photo and describe the current scene"
- "Use the camera to see what's in the room"
- "Take a photo to analyze this environment"
- "Look at the surroundings"
- "Describe this scene"
- "Analyze the environment here"

**Text Recognition:**
- "Take a photo to recognize the text on this document"
- "Use the camera to read the information on this label"
- "Take a photo to translate this English text"
- "Read this text"
- "Recognize text content"
- "Help me read this"
- "Translate this text"
- "Extract text information"

**Problem Solving:**
- "Take a photo to help me solve this problem"
- "Use the camera to analyze this chart"
- "Take a photo to explain what this sign means"
- "How to solve this problem"
- "Analyze this chart"
- "Explain this sign"
- "Help me answer this question"

**Daily Life Assistant:**
- "Take a photo to identify the species of this plant"
- "Use the camera to look at this recipe"
- "Take a photo to help me identify this product"
- "What plant is this"
- "Identify this flower"
- "Look at this recipe"
- "What product is this"
- "Help me check this product"

### Usage Tips

1. **Ensure Adequate Lighting**: Good lighting conditions help improve recognition accuracy
2. **Keep Steady**: Keep the device as steady as possible when taking photos to avoid blur
3. **Be Specific**: Describe in detail what you want to know, e.g., "Identify this plant" rather than "What is this"
4. **Appropriate Distance**: Maintain an appropriate shooting distance to ensure the target object is clearly visible

The AI assistant will automatically invoke the camera tool based on your needs, capturing images and performing intelligent analysis.

## Feature Overview

### Image Capture Features
- **Smart Photo Capture**: Automatically adjust camera parameters to capture clear images
- **Size Optimization**: Automatically resize images to improve processing efficiency
- **Format Conversion**: Convert images to standard JPEG format

### Visual Analysis Features
- **Object Recognition**: Identify objects and scenes in images
- **Text Recognition**: Extract text content from images
- **Scene Understanding**: Analyze image content and provide descriptions
- **Problem Solving**: Answer user questions based on image content

### Device Management Features
- **Camera Configuration**: Automatically detect and configure camera devices
- **Parameter Adjustment**: Support resolution, frame rate, and other parameter settings
- **Error Handling**: Comprehensive error handling and recovery mechanisms

## Tool List

### 1. Image Capture and Analysis Tool

#### take_photo - Take Photo and Analyze
Capture an image and perform intelligent analysis.

**Parameters:**
- `question` (optional): A specific question or analysis requirement about the image

**Use Cases:**
- Object recognition
- Scene analysis
- Text recognition
- Problem solving
- Daily life assistant

## Usage Examples

### Basic Photo Analysis Examples

```python
# Simple photo analysis
result = await mcp_server.call_tool("take_photo", {
    "question": "What object is this?"
})

# Scene description
result = await mcp_server.call_tool("take_photo", {
    "question": "Describe this scene"
})

# Text recognition
result = await mcp_server.call_tool("take_photo", {
    "question": "Recognize the text content in the image"
})

# Problem solving
result = await mcp_server.call_tool("take_photo", {
    "question": "How to solve this math problem?"
})
```

## Technical Architecture

### Camera Management
- **Container injection**: `McpPlugin` creates the camera and calls `register_camera_tools` (no global singleton)
- **Pluggable capture backends** (`src/mcp/tools/camera/capture_backend.py`):
  - **OpenCV / V4L2**: Desktop USB; on Linux prefers `CAP_V4L2`
  - **picamera2**: Raspberry Pi official CSI (Bookworm libcamera stack)
  - **`backend=auto`**: try OpenCV first, then fall back to picamera2
- **Warm-up frames**: drop a few frames after open (USB/Pi often return empty early frames)
- **Timeout**: capture runs in a thread pool so a stuck driver cannot hang the app forever
- **Resource lifecycle**: open → read → release/stop per shot (no long-lived exclusive hold)

### Image Processing
- **OpenCV encode**: resize (default max side 320) and JPEG-encode
- **Format optimization**: smaller upload payload

### Vision Service
- **Remote analysis**: `NormalCamera` + explain URL
- **Zhipu VL**: when both `VLapi_key` and `Local_VL_url` are set → `VLCamera`
- **Authentication**: Token and device ID
- **Errors**: capture/network failures return JSON error messages

## Configuration

### Camera Configuration
Camera-related settings are located in the configuration file:

```json
{
  "CAMERA": {
    "backend": "auto",
    "device": "",
    "camera_index": 0,
    "frame_width": 640,
    "frame_height": 480,
    "fps": 30,
    "warm_up_frames": 5,
    "Local_VL_url": "https://open.bigmodel.cn/api/paas/v4/",
    "VLapi_key": "",
    "models": "glm-4v-plus"
  }
}
```

**Configuration Items:**

| Key | Type | Default | Description |
| --- | ---- | ------- | ----------- |
| `backend` | String | `"auto"` | `auto` / `opencv` / `picamera2` |
| `device` | String | `""` | Path such as `"/dev/video0"`; overrides `camera_index` when set |
| `camera_index` | Integer | `0` | OpenCV device index (desktop) |
| `frame_width` / `frame_height` | Integer | 640 / 480 | Preferred resolution (driver may fall back) |
| `warm_up_frames` | Integer | `5` | Frames to discard after open |
| `Local_VL_url` / `VLapi_key` / `models` | — | — | Optional Zhipu-style VL analysis |

### Platform / Backend Guide

| Scenario | Recommendation |
| -------- | ---------------- |
| macOS / Windows built-in or USB | `backend=auto` or `opencv`, use `camera_index` |
| Linux / Pi **USB UVC** | `backend=opencv`, set `device` to `/dev/videoX` |
| Pi **official CSI** | install system `python3-picamera2`, `backend=auto` or `picamera2` |
| **Do not** pip-install picamera2 on macOS | pulls `python-prctl` and breaks the build |

### Scan & Test Capture

```bash
python scripts/camera_scanner.py
python scripts/camera_scanner.py --test
python scripts/camera_scanner.py --select 0 --test
python scripts/camera_scanner.py --device /dev/video0 --test
python scripts/camera_scanner.py --backend picamera2 --test
```

GUI: Settings → Camera → Refresh → pick **Camera N / V4L2 path / Pi CSI** → Test.

### Vision Service Configuration
The visual analysis service requires configuration of:
- **Service URL**: explain URL or VL base URL
- **Authentication**: Token or API key
- **Device Information**: Device ID and client ID

## Data Structures

### Image Data Format
```python
{
    "buf": bytes,      # JPEG image byte data
    "len": int         # Data length
}
```

### Analysis Result Format
```python
{
    "success": bool,           # Whether the operation was successful
    "message": str,            # Result message or error message
    "analysis": {              # Analysis result (on success)
        "objects": [...],      # Recognized objects
        "text": str,           # Extracted text
        "description": str,    # Scene description
        "answer": str          # Answer to question
    }
}
```

## Image Processing Flow

### 1. Image Capture
1. Choose backend from `CAMERA.backend` / `device` / `camera_index`
2. OpenCV: open (V4L2 on Linux) → try resolution → warm-up → read a valid frame
3. Or picamera2: still config → start → warm-up → `capture_array` → convert to BGR
4. Resize, JPEG-encode, release the device

### 2. Image Preprocessing
1. Obtain image dimensions
2. Calculate scaling ratio (longest edge not exceeding 320 pixels)
3. Scale image proportionally
4. Convert to JPEG format

### 3. Visual Analysis
1. Prepare request headers
2. Build multimedia request
3. Send to visual analysis service
4. Parse analysis results

## Best Practices

### 1. Image Quality Optimization
- Ensure adequate lighting conditions
- Keep the camera lens clean
- Avoid overexposure or darkness
- Keep the subject clear

### 2. Question Description Tips
- Use specific and clear questions
- Avoid vague expressions
- Provide contextual information
- Indicate the focus of analysis

### 3. Performance Optimization
- Set appropriate image resolution
- Avoid frequent photo capture
- Release resources promptly
- Handle network timeouts

### 4. Error Handling
- Check camera availability
- Handle network connection errors
- Validate analysis results
- Provide user-friendly error messages

## Supported Analysis Types

### Object Recognition
- Everyday item recognition
- Animal and plant recognition
- Food recognition
- Product recognition

### Text Recognition
- Printed text recognition
- Handwritten text recognition
- Multi-language text recognition
- Document content extraction

### Scene Understanding
- Indoor scene analysis
- Outdoor environment description
- Human action recognition
- Activity scene understanding

### Problem Solving
- Math problem solving
- Chart analysis
- Sign explanation
- Technical problems

## Notes

1. **Privacy Protection**: The photo capture feature involves privacy; please use with caution
2. **Network Dependency**: Visual analysis requires a network connection
3. **Device Permissions**: Camera access permission is required
4. **Processing Time**: Image analysis may take some time

## Troubleshooting

### Common Issues
1. **Camera cannot open**: connection, permissions (Linux `video` group), `camera_index` / `device`
2. **Works on PC, fails on Pi CSI**: need libcamera + `python3-picamera2`, not bare `VideoCapture(0)`
3. **Index 0 fails on Pi**: check `ls /dev/video*`, set `--device /dev/videoX` or another index
4. **Opens but black/empty frame**: increase `warm_up_frames` or relax resolution
5. **Analysis fails**: network, explain URL / VL key
6. **macOS uv fails on picamera2 / python-prctl**: never install picamera2 on Mac; use apt only on Pi

### Debugging Methods
```bash
ls -l /dev/video*
groups   # should include video
rpicam-hello -t 1000   # or libcamera-hello

python scripts/camera_scanner.py --test
```

With the camera tool, you can easily achieve intelligent visual recognition and image analysis, bringing convenience to daily life and work.
