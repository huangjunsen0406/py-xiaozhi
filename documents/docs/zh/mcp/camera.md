# 摄像头工具 (Camera Tools)

摄像头工具是一个智能视觉识别 MCP 工具，提供了图像捕获、视觉分析和图像理解等功能。

### 常见使用场景

**图像识别分析:**
- "帮我拍张照片看看这是什么"
- "拍照识别一下这个物体"
- "用摄像头看看我面前是什么东西"
- "看看这个东西是什么"
- "识别一下这个是什么"
- "帮我看看这个"
- "拍照分析这个物品"

**场景理解:**
- "拍照描述一下现在的场景"
- "用摄像头看看房间里有什么"
- "拍照分析一下这个环境"
- "看看周围的情况"
- "描述一下这个场景"
- "分析一下这里的环境"

**文字识别:**
- "拍照识别这个文档上的文字"
- "用摄像头读取这个标签上的信息"
- "拍照翻译这段英文"
- "读取这个文字"
- "识别文字内容"
- "帮我读一下这个"
- "翻译这段文字"
- "提取文字信息"

**问题解答:**
- "拍照帮我看看这道题怎么做"
- "用摄像头分析这个图表"
- "拍照解释这个标志是什么意思"
- "这道题怎么解"
- "分析这个图表"
- "解释这个标志"
- "帮我解答这个问题"

**生活助手:**
- "拍照识别这个植物的品种"
- "用摄像头看看这个菜谱"
- "拍照帮我识别这个商品"
- "这是什么植物"
- "识别这个花"
- "看看这个菜谱"
- "这个商品是什么"
- "帮我看看这个产品"

### 使用提示

1. **确保光线充足**: 良好的光线条件有助于提高识别准确率
2. **保持稳定**: 拍照时尽量保持设备稳定，避免模糊
3. **明确问题**: 详细描述您想了解的内容，如"识别这个植物"而不是"这是什么"
4. **合适距离**: 保持适当的拍摄距离，确保目标物体清晰可见

AI 助手会根据您的需求自动调用摄像头工具，捕获图像并进行智能分析。

## 功能概览

### 图像捕获功能
- **智能拍照**: 自动调节摄像头参数，捕获清晰图像
- **尺寸优化**: 自动调整图像尺寸，提高处理效率
- **格式转换**: 将图像转换为标准JPEG格式

### 视觉分析功能
- **物体识别**: 识别图像中的物体和场景
- **文字识别**: 提取图像中的文字内容
- **场景理解**: 分析图像内容并提供描述
- **问题解答**: 基于图像内容回答用户问题

### 设备管理功能
- **摄像头配置**: 自动检测和配置摄像头设备
- **参数调节**: 支持分辨率、帧率等参数设置
- **错误处理**: 完善的错误处理和恢复机制

## 工具列表

### 1. 图像捕获与分析工具

#### take_photo - 拍照并分析
捕获图像并进行智能分析。

**参数:**
- `question` (可选): 对图像的具体问题或分析需求

**使用场景:**
- 物体识别
- 场景分析
- 文字识别
- 问题解答
- 生活助手

## 使用示例

### 基础拍照分析示例

```python
# 简单拍照分析
result = await mcp_server.call_tool("take_photo", {
    "question": "这是什么物体？"
})

# 场景描述
result = await mcp_server.call_tool("take_photo", {
    "question": "描述一下这个场景"
})

# 文字识别
result = await mcp_server.call_tool("take_photo", {
    "question": "识别图片中的文字内容"
})

# 问题解答
result = await mcp_server.call_tool("take_photo", {
    "question": "这道数学题怎么解？"
})
```

## 技术架构

### 摄像头管理
- **容器注入**: 由 `McpPlugin` 创建 camera 实例并 `register_camera_tools`，不使用全局单例
- **可插拔采集后端** (`src/mcp/tools/camera/capture_backend.py`):
  - **OpenCV / V4L2**: 桌面 USB、Linux USB（Linux 优先 `CAP_V4L2`）
  - **picamera2**: 树莓派官方 CSI（Bookworm libcamera 栈）
  - **`backend=auto`**: 先 OpenCV，失败再回退 picamera2
- **预热帧**: 打开设备后丢弃若干帧再取图（USB / Pi 前几帧常无效）
- **超时保护**: 采集在线程池中执行，避免驱动挂死拖死主流程
- **资源管理**: 每次拍照 open → 读帧 → release / stop，不长期占设备

### 图像处理
- **OpenCV 编码**: 采集后缩放（默认最长边 320）并编码为 JPEG
- **格式优化**: JPEG 降低上传体积

### 视觉服务
- **远程分析**: 支持连接远程视觉分析服务（`NormalCamera`）
- **智谱 VL**: 配置 `VLapi_key` + `Local_VL_url` 时使用 `VLCamera`
- **身份验证**: Token 和设备 ID
- **错误处理**: 网络与采集失败返回 JSON 错误信息

## 配置说明

### 摄像头配置
摄像头相关配置位于配置文件中：

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

**配置项说明:**

| 配置项 | 类型 | 默认 | 说明 |
| ------ | ---- | ---- | ---- |
| `backend` | String | `"auto"` | `auto` / `opencv` / `picamera2` |
| `device` | String | `""` | 设备路径，如 `"/dev/video0"`；非空时优先于 `camera_index` |
| `camera_index` | Integer | `0` | OpenCV 设备索引（桌面常用） |
| `frame_width` / `frame_height` | Integer | 640 / 480 | 期望分辨率（驱动可能回落） |
| `warm_up_frames` | Integer | `5` | 打开后丢弃的预热帧数 |
| `Local_VL_url` / `VLapi_key` / `models` | — | — | 智谱等多模态 VL；二者都配齐则走 VL 分析 |

### 平台与后端选择

| 场景 | 推荐 |
| ---- | ---- |
| macOS / Windows USB 或内置摄像头 | `backend=auto` 或 `opencv`，用 `camera_index` |
| Linux / 树莓派 **USB UVC** | `backend=opencv`，优先配置 `device` 为 `/dev/videoX` |
| 树莓派 **官方 CSI** | 安装系统 `python3-picamera2`，`backend=auto` 或 `picamera2` |
| 桌面 macOS **不要** pip 安装 picamera2 | 会拉 `python-prctl` 导致构建失败 |

### 扫描与试拍

```bash
# 列出设备；可选写入配置并试拍
python scripts/camera_scanner.py
python scripts/camera_scanner.py --test
python scripts/camera_scanner.py --select 0 --test
python scripts/camera_scanner.py --device /dev/video0 --test
python scripts/camera_scanner.py --backend picamera2 --test
```

GUI：设置 → 摄像头 → 刷新 → 选择 **摄像头 N / V4L2 /dev/videoX / 树莓派 CSI** → 测试。

### 视觉服务配置
视觉分析服务需要配置：
- **服务URL**: 视觉分析服务的接口地址（服务端下发或 VL URL）
- **身份验证**: Token 或 API 密钥
- **设备信息**: 设备 ID 和客户端 ID

## 数据结构

### 图像数据格式
```python
{
    "buf": bytes,      # JPEG图像字节数据
    "len": int         # 数据长度
}
```

### 分析结果格式
```python
{
    "success": bool,           # 是否成功
    "message": str,            # 结果信息或错误信息
    "analysis": {              # 分析结果（成功时）
        "objects": [...],      # 识别的物体
        "text": str,           # 提取的文字
        "description": str,    # 场景描述
        "answer": str          # 问题答案
    }
}
```

## 图像处理流程

### 1. 图像捕获
1. 按 `CAMERA.backend` / `device` / `camera_index` 选择后端
2. OpenCV：打开设备（Linux 优先 V4L2）→ 尝试设分辨率 → 预热帧 → 读有效帧
3. 或 picamera2：still 配置 → start → 预热 → `capture_array` → 转 BGR
4. 缩放并编码 JPEG，释放设备

### 2. 图像预处理
1. 获取图像尺寸信息
2. 计算缩放比例（最长边不超过320像素）
3. 等比例缩放图像
4. 转换为JPEG格式

### 3. 视觉分析
1. 准备请求头信息
2. 构建多媒体请求
3. 发送到视觉分析服务
4. 解析分析结果

## 最佳实践

### 1. 图像质量优化
- 确保充足的光线条件
- 保持摄像头清洁
- 避免过度曝光或阴暗
- 保持拍摄对象清晰

### 2. 问题描述技巧
- 使用具体明确的问题
- 避免模糊不清的表述
- 提供上下文信息
- 指明分析重点

### 3. 性能优化
- 合理设置图像分辨率
- 避免频繁拍照
- 及时释放资源
- 处理网络超时

### 4. 错误处理
- 检查摄像头可用性
- 处理网络连接错误
- 验证分析结果
- 提供用户友好的错误信息

## 支持的分析类型

### 物体识别
- 日常用品识别
- 动植物识别
- 食物识别
- 商品识别

### 文字识别
- 印刷文字识别
- 手写文字识别
- 多语言文字识别
- 文档内容提取

### 场景理解
- 室内场景分析
- 户外环境描述
- 人物动作识别
- 活动场景理解

### 问题解答
- 数学题解答
- 图表分析
- 标志解释
- 技术问题

## 注意事项

1. **隐私保护**: 拍照功能涉及隐私，请谨慎使用
2. **网络依赖**: 视觉分析需要网络连接
3. **设备权限**: 需要摄像头访问权限
4. **处理时间**: 图像分析可能需要一定时间

## 故障排除

### 常见问题
1. **摄像头无法打开**: 检查连接、权限（Linux `video` 组）、`camera_index` / `device`
2. **电脑正常、树莓派 CSI 不行**: CSI 需 libcamera + `python3-picamera2`，不要只靠 `VideoCapture(0)`
3. **Pi 上 index 0 打不开**: 查看 `ls /dev/video*`，用 `--device /dev/videoX` 或换 index
4. **open 成功但黑图/失败**: 增大 `warm_up_frames`，或放宽分辨率
5. **分析失败**: 检查网络、explain URL / VL Key
6. **macOS 上 `uv` 因 picamera2 / python-prctl 失败**: 不要在 Mac 安装 picamera2，仅在 Pi 用 apt

### 调试方法
```bash
# Linux / Pi
ls -l /dev/video*
groups   # 应包含 video
# CSI 系统栈
rpicam-hello -t 1000   # 或 libcamera-hello

python scripts/camera_scanner.py --test
```

通过摄像头工具，您可以轻松实现智能视觉识别和图像分析，为日常生活和工作提供便利。
