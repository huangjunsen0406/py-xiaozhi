"""摄像头采集后端：OpenCV/UVC（桌面+Pi USB）与 Picamera2（Pi CSI）。

桌面 USB 摄像头走 OpenCV；树莓派 CSI 官方栈走 picamera2（可选依赖）。
``backend=auto`` 时先试 OpenCV，失败再回退 picamera2。
"""

from __future__ import annotations

import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeout
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.logging import get_logger
from src.utils.config_manager import get_config

logger = get_logger()

_CAPTURE_TIMEOUT_S = 12.0


@dataclass
class CaptureConfig:
    """采集参数（来自 CAMERA.* 配置）."""

    camera_index: int = 0
    device: str = ""  # 如 /dev/video0；非空时优先于 index
    backend: str = "auto"  # auto | opencv | picamera2
    frame_width: int = 640
    frame_height: int = 480
    warm_up_frames: int = 5
    jpeg_max_side: int = 320


@dataclass
class CameraDeviceInfo:
    """可展示/可选的摄像头条目."""

    key: str  # 写入配置的标识：数字 index 字符串 / 设备路径 / "picamera2"
    name: str
    kind: str  # opencv | v4l2 | picamera2
    index: int | None = None
    path: str | None = None


def load_capture_config() -> CaptureConfig:
    """从 ConfigManager 读取 CAMERA 采集配置."""
    cfg = get_config()
    raw_backend = (
        str(cfg.get_config("CAMERA.backend", "auto") or "auto").strip().lower()
    )
    if raw_backend not in ("auto", "opencv", "picamera2"):
        raw_backend = "auto"

    device = str(cfg.get_config("CAMERA.device", "") or "").strip()
    try:
        index = int(cfg.get_config("CAMERA.camera_index", 0) or 0)
    except (TypeError, ValueError):
        index = 0
    try:
        width = int(cfg.get_config("CAMERA.frame_width", 640) or 640)
    except (TypeError, ValueError):
        width = 640
    try:
        height = int(cfg.get_config("CAMERA.frame_height", 480) or 480)
    except (TypeError, ValueError):
        height = 480
    try:
        warm = int(cfg.get_config("CAMERA.warm_up_frames", 5) or 5)
    except (TypeError, ValueError):
        warm = 5
    warm = max(0, min(warm, 30))

    return CaptureConfig(
        camera_index=max(0, index),
        device=device,
        backend=raw_backend,
        frame_width=max(1, width),
        frame_height=max(1, height),
        warm_up_frames=warm,
    )


def _silence_opencv_logs() -> None:
    os.environ.setdefault("OPENCV_LOG_LEVEL", "ERROR")
    try:
        import cv2

        if hasattr(cv2, "setLogLevel"):
            cv2.setLogLevel(0)
        if hasattr(cv2, "utils") and hasattr(cv2.utils, "logging"):
            cv2.utils.logging.setLogLevel(cv2.utils.logging.LOG_LEVEL_ERROR)
    except Exception:
        pass


def _opencv_open_kwargs():
    """Linux 优先 V4L2，其它平台用默认后端."""
    try:
        import cv2

        if sys.platform.startswith("linux") and hasattr(cv2, "CAP_V4L2"):
            return {"apiPreference": cv2.CAP_V4L2}
    except Exception:
        pass
    return {}


def _open_capture(source: Any):
    """打开 VideoCapture；source 为 int index 或设备路径字符串."""
    import cv2

    kwargs = _opencv_open_kwargs()
    if kwargs:
        cap = cv2.VideoCapture(source, kwargs["apiPreference"])
        if cap is not None and cap.isOpened():
            return cap
        try:
            cap.release()
        except Exception:
            pass
    return cv2.VideoCapture(source)


def _encode_bgr_jpeg(frame, max_side: int = 320) -> bytes | None:
    import cv2

    if frame is None or getattr(frame, "size", 0) == 0:
        return None
    height, width = frame.shape[:2]
    max_dim = max(height, width)
    if max_side > 0 and max_dim > max_side:
        scale = max_side / max_dim
        frame = cv2.resize(
            frame,
            (int(width * scale), int(height * scale)),
            interpolation=cv2.INTER_AREA,
        )
    ok, buf = cv2.imencode(".jpg", frame)
    if not ok:
        return None
    return buf.tobytes()


def _bgr_from_picamera_array(arr):
    """Picamera2 默认常为 RGB/XRGB，转成 OpenCV BGR."""
    import cv2
    import numpy as np

    if arr is None:
        return None
    if arr.ndim == 2:
        return cv2.cvtColor(arr, cv2.COLOR_GRAY2BGR)
    if arr.shape[2] == 4:
        # XRGB / BGRA 等：按 RGB 通道取前 3 再转 BGR（picamera2 常见 RGB）
        rgb = arr[:, :, :3]
        return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    if arr.shape[2] == 3:
        return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
    return np.ascontiguousarray(arr)


def _capture_opencv(cfg: CaptureConfig) -> bytes | None:
    _silence_opencv_logs()
    import cv2

    source: Any
    if cfg.device:
        source = cfg.device
        logger.info(f"OpenCV 打开设备路径: {source}")
    else:
        source = int(cfg.camera_index)
        logger.info(f"OpenCV 打开 index: {source}")

    cap = _open_capture(source)
    if not cap.isOpened():
        logger.error(f"OpenCV 无法打开摄像头 source={source!r}")
        return None

    try:
        # 分辨率：尽力设置，失败不视为致命
        if cfg.frame_width > 0:
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, cfg.frame_width)
        if cfg.frame_height > 0:
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, cfg.frame_height)

        frame = None
        ret = False
        # 预热：很多 USB/Pi 设备前几帧无效
        loops = max(1, cfg.warm_up_frames + 1)
        for i in range(loops):
            ret, frame = cap.read()
            if ret and frame is not None and getattr(frame, "size", 0) > 0:
                # 再多读一帧有时更稳，但已有有效帧可提前结束预热尾部
                if i >= max(0, cfg.warm_up_frames - 1):
                    break
            time.sleep(0.03)

        if not ret or frame is None:
            logger.error(f"OpenCV 读帧失败 source={source!r}")
            return None

        jpeg = _encode_bgr_jpeg(frame, cfg.jpeg_max_side)
        if not jpeg:
            logger.error("OpenCV JPEG 编码失败")
            return None
        logger.info(
            f"OpenCV 采集成功 source={source!r} size={len(jpeg)} "
            f"backend={cap.getBackendName() if hasattr(cap, 'getBackendName') else '?'}"
        )
        return jpeg
    finally:
        try:
            cap.release()
        except Exception:
            pass


def _picamera2_available() -> bool:
    if not sys.platform.startswith("linux"):
        return False
    try:
        import picamera2  # noqa: F401

        return True
    except Exception:
        return False


def _capture_picamera2(cfg: CaptureConfig) -> bytes | None:
    if not sys.platform.startswith("linux"):
        logger.error("picamera2 仅支持 Linux/树莓派")
        return None
    try:
        from picamera2 import Picamera2
    except ImportError:
        logger.error(
            "未安装 picamera2，无法使用 CSI 摄像头。Pi 上: sudo apt install python3-picamera2"
        )
        return None

    picam2 = None
    try:
        picam2 = Picamera2()
        # still 配置；尺寸尽量贴近配置，驱动会选最接近 mode
        controls = {}
        config = picam2.create_still_configuration(
            main={"size": (cfg.frame_width, cfg.frame_height)},
            controls=controls,
        )
        picam2.configure(config)
        picam2.start()
        # 给 AE/AWB 一点时间
        time.sleep(0.2)
        for _ in range(max(1, cfg.warm_up_frames)):
            try:
                picam2.capture_array()
            except Exception:
                time.sleep(0.05)
        arr = picam2.capture_array()
        bgr = _bgr_from_picamera_array(arr)
        jpeg = _encode_bgr_jpeg(bgr, cfg.jpeg_max_side)
        if not jpeg:
            logger.error("picamera2 JPEG 编码失败")
            return None
        logger.info(f"picamera2 采集成功 size={len(jpeg)}")
        return jpeg
    except Exception as e:
        logger.error(f"picamera2 采集失败: {e}", exc_info=True)
        return None
    finally:
        if picam2 is not None:
            try:
                picam2.stop()
            except Exception:
                pass
            try:
                picam2.close()
            except Exception:
                pass


def capture_jpeg(cfg: CaptureConfig | None = None) -> bytes | None:
    """按配置采集一帧 JPEG 字节；失败返回 None."""
    cfg = cfg or load_capture_config()
    backend = cfg.backend

    def _run() -> bytes | None:
        if backend == "opencv":
            return _capture_opencv(cfg)
        if backend == "picamera2":
            return _capture_picamera2(cfg)

        # auto：先 OpenCV（USB/UVC），再 picamera2（CSI）
        jpeg = _capture_opencv(cfg)
        if jpeg:
            return jpeg
        if _picamera2_available():
            logger.info("OpenCV 采集失败，auto 回退 picamera2（CSI）")
            return _capture_picamera2(cfg)
        return None

    with ThreadPoolExecutor(max_workers=1) as pool:
        fut = pool.submit(_run)
        try:
            return fut.result(timeout=_CAPTURE_TIMEOUT_S)
        except FuturesTimeout:
            logger.error(
                f"摄像头采集超时 ({_CAPTURE_TIMEOUT_S}s) "
                f"backend={backend} device={cfg.device!r} index={cfg.camera_index}"
            )
            return None


def _list_v4l2_paths() -> list[str]:
    if not sys.platform.startswith("linux"):
        return []
    dev = Path("/dev")
    if not dev.exists():
        return []
    paths = sorted(
        str(p)
        for p in dev.glob("video*")
        if p.name.startswith("video") and p.name[5:].isdigit()
    )
    return paths


def list_camera_devices(
    max_index: int = 5,
    consecutive_fail_limit: int = 2,
) -> list[CameraDeviceInfo]:
    """枚举可用摄像头（设置页 / 扫描脚本）."""
    _silence_opencv_logs()
    devices: list[CameraDeviceInfo] = []
    seen: set[str] = set()

    # 1) Linux：/dev/video* 优先列出（便于 Pi 选对节点）
    for path in _list_v4l2_paths():
        try:

            cap = _open_capture(path)
            opened = bool(cap.isOpened())
            if opened:
                # 尝试读一帧判断是否为真正 capture 节点
                ok = False
                try:
                    for _ in range(2):
                        ret, frame = cap.read()
                        if ret and frame is not None and getattr(frame, "size", 0) > 0:
                            ok = True
                            break
                except Exception:
                    ok = False
                cap.release()
                if ok:
                    key = path
                    if key not in seen:
                        devices.append(
                            CameraDeviceInfo(
                                key=key,
                                name=f"V4L2 {path}",
                                kind="v4l2",
                                path=path,
                            )
                        )
                        seen.add(key)
            else:
                try:
                    cap.release()
                except Exception:
                    pass
        except Exception as e:
            logger.debug(f"探测 {path} 失败: {e}")

    # 2) OpenCV 数字 index（全平台）
    consecutive_fail = 0
    for i in range(max(0, max_index) + 1):
        try:
            cap = _open_capture(i)
            opened = bool(cap.isOpened())
            if opened:
                key = str(i)
                # 若已通过 /dev/video{i} 列出则跳过重复
                path_alias = f"/dev/video{i}"
                if key not in seen and path_alias not in seen:
                    devices.append(
                        CameraDeviceInfo(
                            key=key,
                            name=f"摄像头 {i}",
                            kind="opencv",
                            index=i,
                        )
                    )
                    seen.add(key)
                try:
                    cap.release()
                except Exception:
                    pass
                consecutive_fail = 0
            else:
                consecutive_fail += 1
                try:
                    cap.release()
                except Exception:
                    pass
                if consecutive_fail >= consecutive_fail_limit:
                    break
        except Exception as e:
            consecutive_fail += 1
            logger.debug(f"探测 index={i} 失败: {e}")
            if consecutive_fail >= consecutive_fail_limit:
                break

    # 3) 树莓派 CSI
    if _picamera2_available():
        key = "picamera2"
        if key not in seen:
            devices.append(
                CameraDeviceInfo(
                    key=key,
                    name="树莓派 CSI (picamera2)",
                    kind="picamera2",
                )
            )
            seen.add(key)

    logger.info(f"摄像头枚举完成: {len(devices)} 个 {[d.name for d in devices]}")
    return devices


def apply_device_selection(key: str) -> dict[str, Any]:
    """根据枚举 key 生成应写入的配置片段.

    Returns:
        可 update 的 dict：camera_index / device / backend
    """
    key = (key or "").strip()
    if key == "picamera2":
        return {
            "CAMERA.backend": "picamera2",
            "CAMERA.device": "",
            "CAMERA.camera_index": 0,
        }
    if key.startswith("/dev/"):
        return {
            "CAMERA.backend": "opencv",
            "CAMERA.device": key,
            "CAMERA.camera_index": 0,
        }
    try:
        idx = int(key)
    except ValueError:
        idx = 0
    return {
        "CAMERA.backend": "auto",
        "CAMERA.device": "",
        "CAMERA.camera_index": idx,
    }
