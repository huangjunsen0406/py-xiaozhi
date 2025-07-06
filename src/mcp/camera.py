import requests
import logging
import threading
import cv2
import base64
from src.utils.config_manager import ConfigManager


class Camera:
    _instance = None
    _lock = threading.Lock()  # 线程安全

    def __init__(self):
        self.explain_url = ""
        self.explain_token = ""
        self.jpeg_data = {
            'buf': b'',  # 图像的JPEG字节数据
            'len': 0     # 字节数据长度
        }

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def set_explain_url(self, url):
        self.explain_url = url

    def set_explain_token(self, token):
        self.explain_token = token

    def set_jpeg_data(self, data_bytes):
        self.jpeg_data['buf'] = data_bytes
        self.jpeg_data['len'] = len(data_bytes)

    def capture(self) -> bool:
        try:
            logging.info("Accessing Windows webcam...")

            cap = cv2.VideoCapture(0)  # 0 表示默认摄像头
            if not cap.isOpened():
                logging.error("Cannot open webcam")
                exit()

            ret, frame = cap.read()
            cap.release()

            if not ret:
                logging.error("Failed to capture image")
                exit()

            # 获取原始图像尺寸
            height, width = frame.shape[:2]

            # 计算缩放比例，使最长边为320
            max_dim = max(height, width)
            scale = 320 / max_dim if max_dim > 320 else 1.0

            # 等比例缩放图像
            if scale < 1.0:
                new_width = int(width * scale)
                new_height = int(height * scale)
                frame = cv2.resize(frame, (new_width, new_height), interpolation=cv2.INTER_AREA)

            # 保存图像为 JPEG 格式
            image = "camera.jpg"
            cv2.imwrite(image, frame)
            # 读取图片并转换为base64
            with open(image, "rb") as image_file:
                decoded = image_file.read()
                # decoded = base64.b64encode(image_data)
            if not decoded:
                logging.error("Failed to decode base64 image data")
                return False

            self.jpeg_data['buf'] = decoded
            self.jpeg_data['len'] = len(decoded)
            logging.info("Image saved to camera.jpg")
            return True
        except Exception as e:
            logging.error(f"Exception during capture: {e}")
            return False

    def get_mac_address(self):
        return "00:11:22:33:44:55"

    def get_uuid(self):
        return "example-uuid"

    def explain(self, question: str) -> str:
        if not self.explain_url:
            return '{"success": false, "message": "Image explain URL or token is not set"}'

        if not self.jpeg_data['buf']:
            return '{"success": false, "message": "Camera buffer is empty"}'

        headers = {
            "Device-Id": ConfigManager.get_instance().get_device_id(),
            "Client-Id": self.get_uuid()
        }

        if self.explain_token:
            headers["Authorization"] = f"Bearer {self.explain_token}"

        files = {
            "question": (None, question),
            "file": ("camera.jpg", self.jpeg_data['buf'], "image/jpeg")
        }
        # logging.info(f"explain_url={self.explain_url}, headers={headers}\n{files}")

        try:
            response = requests.post(
                self.explain_url,
                headers=headers,
                files=files,
                timeout=10
            )
        except requests.RequestException as e:
            logging.error(f"Failed to connect to explain URL: {e}")
            return '{"success": false, "message": "Failed to connect to explain URL"}'

        if response.status_code != 200:
            logging.error(f"Failed to upload photo, status code: {response.status_code}")
            return '{"success": false, "message": "Failed to upload photo"}'

        logging.info(f"Explain image size={self.jpeg_data['len']}, question={question}\n{response.text}")
        return response.text
