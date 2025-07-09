"""
VL camera implementation using Zhipu AI.
"""

import base64

import cv2
from openai import OpenAI

from src.utils.config_manager import ConfigManager
from src.utils.logging_config import get_logger

from .base_camera import BaseCamera

logger = get_logger(__name__)


class VLCamera(BaseCamera):
    """
    智普AI摄像头实现.
    """

    _instance = None

    def __init__(self):
        """
        初始化智普AI摄像头.
        """
        super().__init__()
        config = ConfigManager.get_instance()

        # 初始化OpenAI客户端
        self.client = OpenAI(
            api_key=config.get_config("CAMERA.VLapi_key"),
            base_url=config.get_config(
                "CAMERA.Local_VL_url",
                "https://open.bigmodel.cn/api/paas/v4/chat/completions",
            ),
        )
        self.model = config.get_config("CAMERA.models", "glm-4v-plus")
        logger.info(f"VL Camera initialized with model: {self.model}")

    @classmethod
    def get_instance(cls):
        """
        获取单例实例.
        """
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def capture(self) -> bool:
        """
        捕获图像.
        """
        try:
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
            logger.error(f"Exception during capture: {e}")
            return False

    def analyze(self, question: str) -> str:
        """
        使用智普AI分析图像.
        """
        try:
            if not self.jpeg_data["buf"]:
                return '{"success": false, "message": "Camera buffer is empty"}'

            # 将图像转换为Base64
            image_base64 = base64.b64encode(self.jpeg_data["buf"]).decode("utf-8")

            # 准备消息
            messages = [
                {"role": "system", "content": "You are a helpful assistant."},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_base64}"
                            },
                        },
                        {
                            "type": "text",
                            "text": (
                                question
                                if question
                                else "图中描绘的是什么景象？请详细描述。"
                            ),
                        },
                    ],
                },
            ]

            # 发送请求
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                modalities=["text"],
                stream=True,
                stream_options={"include_usage": True},
            )

            # 收集响应
            result = ""
            for chunk in completion:
                if chunk.choices:
                    result += chunk.choices[0].delta.content or ""

            # 记录响应
            logger.info(f"VL analysis completed, question={question}")
            return f'{{"success": true, "text": "{result}"}}'

        except Exception as e:
            error_msg = f"Failed to analyze image with VL: {str(e)}"
            logger.error(error_msg)
            return f'{{"success": false, "message": "{error_msg}"}}'
