"""摄像头枚举与测试."""

from PySide6.QtCore import Slot

from src.logging import get_logger

logger = get_logger()


class SettingsCameraDevicesMixin:
    # ========== 摄像头设备列表 ==========

    # 最多探测到该 index（含）；连续失败达到阈值则提前结束
    _CAMERA_MAX_INDEX = 5
    _CAMERA_MAX_CONSECUTIVE_FAIL = 2

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
        """执行摄像头扫描（后台线程；早停 + 压低 OpenCV 日志噪声）."""
        cameras: list[dict] = []
        try:
            import os

            # 压低 OpenCV 对无效 index 的 stderr 刷屏
            os.environ.setdefault("OPENCV_LOG_LEVEL", "ERROR")
            import cv2

            try:
                # OpenCV 4.x
                if hasattr(cv2, "setLogLevel"):
                    cv2.setLogLevel(0)
                if hasattr(cv2, "utils") and hasattr(cv2.utils, "logging"):
                    cv2.utils.logging.setLogLevel(cv2.utils.logging.LOG_LEVEL_ERROR)
            except Exception:
                pass

            preferred = int(self._get_value("CAMERA.camera_index", 0) or 0)
            preferred = max(0, min(preferred, self._CAMERA_MAX_INDEX))
            # 先试配置中的 index，再扫其余；连续失败则停
            order = [preferred] + [
                i for i in range(self._CAMERA_MAX_INDEX + 1) if i != preferred
            ]

            consecutive_fail = 0
            for i in order:
                try:
                    cap = cv2.VideoCapture(i)
                    opened = bool(cap.isOpened())
                    if opened:
                        cameras.append({"index": i, "name": f"摄像头 {i}"})
                        cap.release()
                        consecutive_fail = 0
                    else:
                        consecutive_fail += 1
                        try:
                            cap.release()
                        except Exception:
                            pass
                        # 已有成功设备后，连续失败达到阈值则认为后面没有了
                        # 一个都没有时，也在连续失败达到阈值后放弃（避免 0–9 全扫）
                        if consecutive_fail >= self._CAMERA_MAX_CONSECUTIVE_FAIL:
                            break
                except Exception as e:
                    consecutive_fail += 1
                    logger.debug(f"探测摄像头 index={i} 失败: {e}")
                    if consecutive_fail >= self._CAMERA_MAX_CONSECUTIVE_FAIL:
                        break

            logger.info(
                f"摄像头扫描完成: 找到 {len(cameras)} 个 "
                f"(探测上限 index≤{self._CAMERA_MAX_INDEX}, 连续失败早停)"
            )
        except ImportError:
            logger.warning("cv2 未安装，无法扫描摄像头")
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
                else "未检测到摄像头"
            )

    @Slot(result=list)
    def getCameras(self) -> list:
        """获取摄像头列表（不自动触发扫描；由设置页/刷新触发）."""
        return [c["name"] for c in self._cameras]

    @Slot()
    def refreshCameras(self):
        """刷新摄像头列表（非阻塞）."""
        self._load_cameras(force=True)

    def _get_selectedCameraIndex(self) -> int:
        """获取当前选中的摄像头索引."""
        current_idx = self._get_value("CAMERA.camera_index", 0)
        for i, c in enumerate(self._cameras):
            if c["index"] == current_idx:
                return i
        return 0

    def _set_selectedCameraIndex(self, index: int):
        """设置选中的摄像头."""
        if 0 <= index < len(self._cameras):
            camera = self._cameras[index]
            self._set_value("CAMERA.camera_index", camera["index"])
            logger.info(f"选择摄像头: {camera['name']}")

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
        """执行摄像头测试（异常由 _run_worker 兜底）."""
        try:
            import cv2
        except ImportError:
            self.statusMessage.emit("[错误] cv2 未安装")
            self.testComplete.emit("camera", False)
            return

        camera_id = camera["index"]
        cap = cv2.VideoCapture(camera_id)

        if not cap.isOpened():
            self.statusMessage.emit("[失败] 无法打开摄像头")
            self.testComplete.emit("camera", False)
            return

        width = self._get_value("CAMERA.frame_width", 640)
        height = self._get_value("CAMERA.frame_height", 480)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

        for _ in range(5):
            cap.read()

        ret, frame = cap.read()
        cap.release()

        if not ret or frame is None:
            self.statusMessage.emit("[失败] 无法捕获图像")
            self.testComplete.emit("camera", False)
            return

        actual_height, actual_width = frame.shape[:2]
        self.statusMessage.emit(
            f"[成功] 摄像头正常 (分辨率: {actual_width}x{actual_height})"
        )
        self.testComplete.emit("camera", True)
