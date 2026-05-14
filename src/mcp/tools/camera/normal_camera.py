"""
Normal camera implementation using remote API.
"""

import json

import requests

from src.logging import get_logger
from src.utils.config_manager import ConfigManager

from .base_camera import BaseCamera

logger = get_logger()


class NormalCamera(BaseCamera):
    """
    普通摄像头实现，使用远程API进行分析.
    """

    def __init__(self):
        """
        初始化普通摄像头.
        """
        super().__init__()
        self.explain_url = ""
        self.explain_token = ""

    def set_explain_url(self, url: str):
        self.explain_url = url
        logger.info(f"Vision service URL set to: {url}")

    def set_explain_token(self, token: str):
        self.explain_token = token
        if token:
            logger.info("Vision service token has been set")

    def capture(self) -> bool:
        """
        捕获图像（使用基类的通用实现）.
        """
        return self.capture_with_cv2()

    def analyze(self, question: str, image_data: bytes | None = None) -> str:
        if not self.explain_url:
            return json.dumps(
                {"success": False, "message": "Image explain URL is not set"}
            )

        buf = image_data if image_data is not None else self.jpeg_data["buf"]
        if not buf:
            return json.dumps(
                {"success": False, "message": "Camera buffer is empty"}
            )

        # 准备请求头
        headers = {
            "Device-Id": ConfigManager.get_instance().get_config(
                "SYSTEM_OPTIONS.DEVICE_ID"
            ),
            "Client-Id": ConfigManager.get_instance().get_config(
                "SYSTEM_OPTIONS.CLIENT_ID"
            ),
        }

        if self.explain_token:
            headers["Authorization"] = f"Bearer {self.explain_token}"

        # 准备文件数据
        files = {
            "question": (None, question),
            "file": ("camera.jpg", buf, "image/jpeg"),
        }

        try:
            logger.info(
                f"[Vision] POST {self.explain_url}, "
                f"question={question}, file_size={len(buf)} bytes"
            )
            response = requests.post(
                self.explain_url, headers=headers, files=files, timeout=10
            )

            # 检查响应状态
            if response.status_code != 200:
                error_msg = (
                    f"Failed to upload photo, status code: {response.status_code}"
                )
                logger.error(error_msg)
                return json.dumps({"success": False, "message": error_msg})

            # 记录响应
            logger.info(
                f"Explain image size={self.jpeg_data['len']}, "
                f"question={question}\n{response.text}"
            )
            return response.text

        except requests.RequestException as e:
            error_msg = f"Failed to connect to explain URL: {e}"
            logger.error(error_msg)
            return json.dumps({"success": False, "message": error_msg})
