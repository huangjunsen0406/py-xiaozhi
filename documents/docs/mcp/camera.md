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
- **Singleton Pattern**: Ensures only one global camera instance exists
- **Thread Safety**: Supports safe access in multi-threaded environments
- **Resource Management**: Automatically manages camera resource acquisition and release

### Image Processing
- **OpenCV Integration**: Uses OpenCV for image capture and processing
- **Smart Scaling**: Automatically adjusts image dimensions for optimal results
- **Format Optimization**: Converts to JPEG format to reduce transmission load

### Vision Service
- **Remote Analysis**: Supports connecting to remote visual analysis services
- **Authentication**: Supports Token and device ID verification
- **Error Handling**: Comprehensive network error handling mechanisms

## Configuration

### Camera Configuration
Camera-related settings are located in the configuration file:

```json
{
  "CAMERA": {
    "camera_index": 0,
    "frame_width": 640,
    "frame_height": 480
  }
}
```

**Configuration Items:**
- `camera_index`: Camera device index, default 0
- `frame_width`: Image width, default 640
- `frame_height`: Image height, default 480

### Vision Service Configuration
The visual analysis service requires configuration of:
- **Service URL**: The interface address of the visual analysis service
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
1. Initialize camera device
2. Set capture parameters (resolution, frame rate, etc.)
3. Capture a single frame
4. Release camera resources

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
1. **Camera Cannot Open**: Check device connection and permissions
2. **Blurry Image**: Check lighting conditions and focus
3. **Analysis Failed**: Check network connection and service status
4. **Inaccurate Results**: Optimize image quality and question description

### Debugging Methods
1. Check camera device status
2. Verify network connection
3. View log error messages
4. Test different shooting conditions

With the camera tool, you can easily achieve intelligent visual recognition and image analysis, bringing convenience to daily life and work.
