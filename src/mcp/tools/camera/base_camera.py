"""
Base camera implementation.
"""

import threading
from abc import ABC, abstractmethod
from typing import Any

from src.logging import get_logger
from src.utils.config_manager import ConfigManager

logger = get_logger()


class BaseCamera(ABC):
    """
    基础摄像头类，定义接口.
    """

    _instances = {}  # 存储各子类的单例实例
    _lock = threading.Lock()

    def __init__(self):
        """
        初始化基础摄像头.
        """
        self.jpeg_data = {"buf": b"", "len": 0}  # 图像的JPEG字节数据  # 字节数据长度

        # 从配置中读取相机参数
        config = ConfigManager.get_instance()
        self.camera_index = config.get_config("CAMERA.camera_index", 0)
        self.frame_width = config.get_config("CAMERA.frame_width", 640)
        self.frame_height = config.get_config("CAMERA.frame_height", 480)

    @classmethod
    def get_instance(cls):
        """
        获取单例实例（所有子类共享此方法）.
        """
        if cls not in cls._instances:
            with cls._lock:
                if cls not in cls._instances:
                    cls._instances[cls] = cls()
        return cls._instances[cls]

    def _do_cv2_capture(self) -> bool:
        """
        在独立线程中执行 cv2 捕获操作（内部实现）.
        """
        try:
            import cv2

            logger.info("Accessing camera...")

            # 尝试打开摄像头
            cap = cv2.VideoCapture(self.camera_index)
            if not cap.isOpened():
                logger.error(f"Cannot open camera at index {self.camera_index}")
                return False

            # 设置摄像头参数
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.frame_width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.frame_height)

            # 读取图像
            ret, frame = cap.read()
            cap.release()

            if not ret:
                logger.error("Failed to capture image")
                return False

            # 获取原始图像尺寸
            height, width = frame.shape[:2]

            # 计算缩放比例，使最长边为320
            max_dim = max(height, width)
            scale = 320 / max_dim if max_dim > 320 else 1.0

            # 等比例缩放图像
            if scale < 1.0:
                new_width = int(width * scale)
                new_height = int(height * scale)
                frame = cv2.resize(
                    frame, (new_width, new_height), interpolation=cv2.INTER_AREA
                )

            # 直接将图像编码为JPEG字节流
            success, jpeg_data = cv2.imencode(".jpg", frame)

            if not success:
                logger.error("Failed to encode image to JPEG")
                return False

            # 保存字节数据
            self.set_jpeg_data(jpeg_data.tobytes())
            logger.info(
                f"Image captured successfully (size: {self.jpeg_data['len']} bytes)"
            )
            return True

        except Exception as e:
            logger.error(f"Exception during capture: {e}", exc_info=True)
            return False

    def capture_with_cv2(self) -> bool:
        """
        使用 OpenCV 捕获图像的通用实现（带超时保护）.

        cv2.VideoCapture 在摄像头被占用或故障时可能长时间挂起，
        通过 ThreadPoolExecutor 包装超时保护。

        Returns:
            成功返回 True，失败返回 False
        """
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(self._do_cv2_capture)
            try:
                return future.result(timeout=10.0)
            except concurrent.futures.TimeoutError:
                logger.error(
                    f"Camera capture timed out after 10s (index={self.camera_index})"
                )
                return False

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
