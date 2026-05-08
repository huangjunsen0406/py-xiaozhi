# 修复 camera 全链路阻塞 qasync 主线程

## Goal

修复 camera 全链路中阻塞 qasync/Qt 主线程的问题，包括 UI 层摄像头扫描和 MCP 工具层超时缺失，确保 GUI 模式下 UI 不卡顿且线程池不被无限挂起。

## What I already know

### 已安全（无需修改）
* MCP `take_photo`（`camera/__init__.py`）已用 `asyncio.to_thread()` 包装 `capture()` + `analyze()` — 安全
* MCP `take_screenshot`（`screenshot/__init__.py`）同样使用 `asyncio.to_thread()` — 安全
* `NormalCamera.analyze()` — `requests.post(timeout=10)` 已有超时 — 安全

### 需要修复（3 个问题）

**P1: `_load_cameras()` 阻塞 Qt 主线程**
* 文件：`src/ui/shared/models/settings_model.py:806-822`
* 问题：在 Qt 主线程同步循环 `cv2.VideoCapture(i)` (i=0..9)，无线程卸载
* 触发：初始化时 + `refreshCameras()` Qt slot
* 影响：启动时 UI 卡顿 ~数秒

**P2: `VLCamera` OpenAI 客户端无超时**
* 文件：`src/mcp/tools/camera/vl_camera.py:30-37`
* 问题：`OpenAI(api_key=..., base_url=...)` 未设 `timeout` 参数
* 影响：智普 AI API 无响应时线程池线程永久挂起
* 注意：虽在 `asyncio.to_thread()` 中运行不阻塞事件循环，但会耗尽线程池

**P3: `capture_with_cv2()` 无超时保护**
* 文件：`src/mcp/tools/camera/base_camera.py:46-107`
* 问题：`cv2.VideoCapture` 在摄像头被占用/故障时可能长时间挂起
* 影响：同上，线程池线程被占用

## Requirements

* `_load_cameras()` 必须在后台线程执行，通过 Qt 信号通知完成
* `VLCamera` OpenAI 客户端必须设置合理超时
* `capture_with_cv2()` 需要超时保护机制

## Acceptance Criteria

* [ ] `_load_cameras()` 的 cv2 扫描在后台线程执行，UI 不卡顿
* [ ] `refreshCameras()` 不会阻塞 UI
* [ ] `VLCamera` OpenAI 客户端有超时配置
* [ ] `capture_with_cv2()` 有超时保护
* [ ] lint / typecheck 通过

## Definition of Done (team quality bar)

* Tests added/updated (unit/integration where appropriate)
* Lint / typecheck / CI green
* Rollout/rollback considered if risky

## Out of Scope (explicit)

* `cv2.VideoCapture` 本身的线程安全问题（opencv 库层面）
* 其他非 camera 的 Qt 主线程阻塞问题
* MCP `take_photo` / `take_screenshot` 的 asyncio.to_thread 模式（已正确）

## Technical Notes

* 参考模式：`testCamera()` 在 settings_model.py:853 已使用 `threading.Thread(daemon=True)`
* qasync 事件循环：`main.py:174` — `qasync.QEventLoop(qt_app)`
* OpenAI SDK timeout: `OpenAI(timeout=httpx.Timeout(30.0, connect=10.0))`
* cv2 超时：可用 `concurrent.futures.ThreadPoolExecutor` + `future.result(timeout=N)` 包装
