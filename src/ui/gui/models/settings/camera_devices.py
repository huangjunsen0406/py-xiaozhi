"""摄像头枚举与测试."""

from PySide6.QtCore import Slot

from src.logging import get_logger

logger = get_logger()


class SettingsCameraDevicesMixin:
    # ========== 摄像头设备列表 ==========

    def _load_cameras(self, force: bool = False):
        """在后台线程加载摄像头列表，避免阻塞 Qt 主线程.

        不在应用启动时调用；仅在打开设置 / 刷新 / 摄像头页时触发。
        """
        if self._cameras_loading:
            return
        if self._cameras_loaded_once and not force and self._cameras:
            return

        self._cameras_loading = True
        self._run_worker(
            self._do_load_cameras,
            name="settings:scan_cameras",
            clear_flags=lambda: setattr(self, "_cameras_loading", False),
        )

    def _do_load_cameras(self):
        """执行摄像头扫描（OpenCV/V4L2 + 可选 picamera2）."""
        cameras: list[dict] = []
        try:
            from src.mcp.tools.camera.capture_backend import list_camera_devices

            devices = list_camera_devices(max_index=5, consecutive_fail_limit=2)
            for d in devices:
                cameras.append(
                    {
                        "key": d.key,
                        "index": d.index if d.index is not None else -1,
                        "name": d.name,
                        "kind": d.kind,
                        "path": d.path,
                    }
                )
            logger.info(f"摄像头扫描完成: 找到 {len(cameras)} 个")
        except Exception as e:
            logger.error(f"扫描摄像头失败: {e}", exc_info=True)
            raise
        finally:
            self._cameras = cameras
            self._cameras_loaded_once = True
            self.devicesChanged.emit()
            self.statusMessage.emit(
                f"摄像头列表已刷新（{len(cameras)} 个）"
                if cameras
                else "未检测到摄像头（Pi CSI 需安装 picamera2）"
            )

    @Slot(result=list)
    def getCameras(self) -> list:
        """获取摄像头列表（不自动触发扫描；由设置页/刷新触发）."""
        return [c["name"] for c in self._cameras]

    @Slot()
    def refreshCameras(self):
        """刷新摄像头列表（非阻塞）."""
        self._load_cameras(force=True)

    def _current_camera_key(self) -> str:
        """从配置还原当前选中的枚举 key."""
        device = str(self._get_value("CAMERA.device", "") or "").strip()
        backend = (
            str(self._get_value("CAMERA.backend", "auto") or "auto").strip().lower()
        )
        if backend == "picamera2":
            return "picamera2"
        if device:
            return device
        try:
            return str(int(self._get_value("CAMERA.camera_index", 0) or 0))
        except (TypeError, ValueError):
            return "0"

    def _get_selectedCameraIndex(self) -> int:
        """获取当前选中的摄像头在列表中的下标."""
        current_key = self._current_camera_key()
        for i, c in enumerate(self._cameras):
            if c.get("key") == current_key:
                return i
        # 兼容旧逻辑：只配了 index
        try:
            current_idx = int(self._get_value("CAMERA.camera_index", 0) or 0)
        except (TypeError, ValueError):
            current_idx = 0
        for i, c in enumerate(self._cameras):
            if c.get("index") == current_idx and c.get("kind") in ("opencv", "v4l2"):
                return i
        return 0

    def _set_selectedCameraIndex(self, index: int):
        """设置选中的摄像头（写入 backend/device/index）."""
        if 0 <= index < len(self._cameras):
            camera = self._cameras[index]
            from src.mcp.tools.camera.capture_backend import apply_device_selection

            updates = apply_device_selection(str(camera.get("key", "")))
            for path, value in updates.items():
                self._set_value(path, value)
            logger.info(f"选择摄像头: {camera['name']} -> {updates}")

    @Slot()
    def testCamera(self):
        """测试摄像头，捕获一帧并显示."""
        if not self._cameras:
            self.statusMessage.emit("没有可用的摄像头")
            return

        idx = self._get_selectedCameraIndex()
        if idx < 0 or idx >= len(self._cameras):
            self.statusMessage.emit("请先选择摄像头")
            return

        camera = self._cameras[idx]
        self.statusMessage.emit(f"正在测试摄像头 {camera['name']}...")

        self._run_worker(
            self._do_camera_test,
            camera,
            name="settings:camera_test",
            test_kind="camera",
        )

    def _do_camera_test(self, camera: dict):
        """执行摄像头测试（走统一 capture_backend）."""
        from src.mcp.tools.camera.capture_backend import (
            CaptureConfig,
            apply_device_selection,
            capture_jpeg,
        )

        updates = apply_device_selection(str(camera.get("key", "")))
        backend = updates.get("CAMERA.backend", "auto")
        device = updates.get("CAMERA.device", "") or ""
        try:
            cam_index = int(updates.get("CAMERA.camera_index", 0) or 0)
        except (TypeError, ValueError):
            cam_index = 0

        try:
            width = int(self._get_value("CAMERA.frame_width", 640) or 640)
            height = int(self._get_value("CAMERA.frame_height", 480) or 480)
            warm = int(self._get_value("CAMERA.warm_up_frames", 5) or 5)
        except (TypeError, ValueError):
            width, height, warm = 640, 480, 5

        cfg = CaptureConfig(
            camera_index=cam_index,
            device=device,
            backend=str(backend),
            frame_width=width,
            frame_height=height,
            warm_up_frames=warm,
            jpeg_max_side=640,
        )
        jpeg = capture_jpeg(cfg)
        if not jpeg:
            self.statusMessage.emit(
                "[失败] 无法捕获图像（Pi CSI 请装 python3-picamera2 或改选 USB）"
            )
            self.testComplete.emit("camera", False)
            return

        self.statusMessage.emit(
            f"[成功] 摄像头正常 (JPEG {len(jpeg)} bytes, {camera['name']})"
        )
        self.testComplete.emit("camera", True)
