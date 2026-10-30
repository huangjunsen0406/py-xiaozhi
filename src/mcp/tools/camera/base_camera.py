"""
Base camera implementation.
"""

from abc import ABC, abstractmethod
from typing import Any

from src.logging import get_logger
from src.utils.config_manager import ConfigManager

from .capture_backend import capture_jpeg, load_capture_config

logger = get_logger()


class BaseCamera(ABC):
    """
    基础摄像头类，定义接口.
    """

    def __init__(self, config=None):
        """初始化基础摄像头；配置由宿主注入。"""
        self.config = config if config is not None else ConfigManager.from_dict()
        self.jpeg_data = {"buf": b"", "len": 0}

        cfg = load_capture_config(self.config)
        self.camera_index = cfg.camera_index
        self.frame_width = cfg.frame_width
        self.frame_height = cfg.frame_height

    def capture_frame(self) -> bool:
        """使用可插拔后端采集一帧 JPEG（OpenCV/V4L2 或 picamera2）.

        桌面 USB / Pi USB 走 OpenCV；Pi CSI 在 auto 模式下 OpenCV 失败后回退 picamera2。
        调用在超时后返回失败；仍阻塞的 native 驱动占用唯一 daemon worker，
        直至驱动返回或进程退出，期间重试返回 busy，不能从 Python 强制终止。
        """
        cfg = load_capture_config(self.config)
        # 与实例字段对齐（外部若改过 index 仍以配置为准，配置是权威）
        self.camera_index = cfg.camera_index
        self.frame_width = cfg.frame_width
        self.frame_height = cfg.frame_height

        jpeg = capture_jpeg(cfg)
        if not jpeg:
            logger.error(
                "摄像头采集失败 "
                f"(backend={cfg.backend}, device={cfg.device!r}, index={cfg.camera_index})"
            )
            return False

        self.set_jpeg_data(jpeg)
        logger.info(
            f"Image captured successfully (size: {self.jpeg_data['len']} bytes)"
        )
        return True

    # 兼容旧名
    def capture_with_cv2(self) -> bool:
        return self.capture_frame()

    def set_explain_url(self, url: str):  # noqa: B027
        """设置视觉服务 URL（子类按需覆写）."""

    def set_explain_token(self, token: str):  # noqa: B027
        """设置视觉服务 token（子类按需覆写）."""

    @abstractmethod
    def capture(self) -> bool:
        """
        捕获图像.
        """

    @abstractmethod
    def analyze(self, question: str, image_data: bytes | None = None) -> str:
        """分析图像.

        Args:
            question: 用户问题
            image_data: 可选的外部图像数据，为 None 时使用 self.jpeg_data
        """

    def get_jpeg_data(self) -> dict[str, Any]:
        """
        获取JPEG数据.
        """
        return self.jpeg_data

    def set_jpeg_data(self, data_bytes: bytes):
        """
        设置JPEG数据.
        """
        self.jpeg_data["buf"] = data_bytes
        self.jpeg_data["len"] = len(data_bytes)
