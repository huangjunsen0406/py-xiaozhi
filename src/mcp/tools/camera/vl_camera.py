"""
VL camera implementation using Zhipu AI.
"""

import base64

from openai import OpenAI

from src.logging import get_logger
from src.utils.config_manager import ConfigManager

from .base_camera import BaseCamera

logger = get_logger()


class VLCamera(BaseCamera):
    """
    智普AI摄像头实现.
    """

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

    def capture(self) -> bool:
        """
        捕获图像（使用基类的通用实现）.
        """
        return self.capture_with_cv2()

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
