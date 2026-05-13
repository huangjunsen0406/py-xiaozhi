# 修复 MCP 模块 JSON 注入、发现容错、相机代码优化

## Goal

修复 MCP 模块中 3 类问题：JSON f-string 注入（可靠性/安全性）、工具自动发现缺少错误处理（健壮性）、相机代码优化（消除线程安全问题和冗余 hasattr 检查）。

## Requirements

### 1. JSON f-string 注入修复
所有手动拼接 JSON 的地方改用 `json.dumps()`：
- `normal_camera.py:95,107` — error_msg 可能含引号
- `vl_camera.py:100,105` — AI 返回的 result 几乎必然含引号
- `screenshot_camera.py:457` — str(e) 可能含引号

### 2. 工具模块自动发现容错
- `decorators.py:118/126/132` — `import_module()` 加 try-except
- 单个工具模块 import 失败只 log warning，不中断其他工具加载

### 3. 相机代码优化
- `screenshot_camera.py:analyze()` 临时替换全局 camera 单例 jpeg_data 的做法有并发竞争风险
- 改为：BaseCamera.analyze 接受可选 `image_data` 参数，ScreenshotCamera 直接传入自己的数据
- 移除 `_parse_capabilities` 中的 hasattr 检查，改为 BaseCamera 提供 no-op 默认实现

### 4. mcp_server.py 顺带修复
- `id` → `request_id` 避免遮蔽内置函数
- `if "id" in locals()` → 提前初始化 `request_id = None`
- error response 补充 `code` 字段（JSON-RPC 2.0 规范）

## Acceptance Criteria

- [ ] 所有 camera/screenshot 工具返回值用 json.dumps 构建
- [ ] 单个工具模块 import 失败不影响其他工具加载
- [ ] ScreenshotCamera.analyze 不再替换全局 camera 单例的 jpeg_data
- [ ] JSON-RPC error response 包含 code 字段

## Out of Scope

- McpTool.call 双重 JSON 序列化优化（影响面大，单独处理）
- 天气工具硬编码数据问题
- 单例线程安全问题（McpServer 只在主线程使用）
