import cv2
import base64
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional
import threading
from src.iot.thing import Thing
from src.iot.things.CameraVL import VL

logger = logging.getLogger("Camera")


class Camera(Thing):
    # 配置文件路径
    CONFIG_DIR = Path(__file__).parent.parent.parent.parent.parent / "config"
    CONFIG_FILE = CONFIG_DIR / "camera_VL_config.json"
    # 默认配置
    DEFAULT_CONFIG = {
        "camera_index": 0,  # 默认摄像头索引
        "frame_width": 640,  # 帧宽度
        "frame_height": 480,  # 帧高度
        "fps": 30,  # 帧率
        "Loacl_VL_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",  # 修改为你对应的llm地址
        "VLapi_key": 'XXXXXX',  # 修改为你的api key
    }
    def __init__(self):
        super().__init__("Camera", "摄像头管理")
        """初始化摄像头管理器"""
        if hasattr(self, '_initialized'):
            return
        self._initialized = True
        # 加载配置
        self._config = self._load_config()
        self.cap = None
        self.is_running = False
        self.camera_thread = None
        self.result=""
        # 摄像头控制器
        self.VL=VL.ImageAnalyzer.get_instance().init(self._config['VLapi_key'], self._config['Loacl_VL_url'])
        self.VL= VL.ImageAnalyzer.get_instance()
        print(f"[虚拟设备] 摄像头设备初始化完成")

        self.add_property_and_method()#定义设备方法与状态属性

    def add_property_and_method(self):
        # 定义属性
        self.add_property("power", "摄像头是否打开", lambda: self.is_running )
        self.add_property("result", "识别画面的内容", lambda: self.result )
        # 定义方法
        self.add_method("start_camera", "打开摄像头", [],
                        lambda params: self.start_camera())

        self.add_method("stop_camera", "关闭摄像头", [],
                        lambda params: self.stop_camera())

        self.add_method("capture_frame_to_base64", "识别画面", [],
                        lambda params: self.capture_frame_to_base64())


    def _load_config(self) -> Dict[str, Any]:
        """加载配置文件，如果不存在则创建"""
        try:
            if self.CONFIG_FILE.exists():
                config = json.loads(self.CONFIG_FILE.read_text(encoding='utf-8'))
                return self._merge_configs(self.DEFAULT_CONFIG, config)
            else:
                # 创建默认配置
                self.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
                self._save_config(self.DEFAULT_CONFIG)
                return self.DEFAULT_CONFIG.copy()
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            return self.DEFAULT_CONFIG.copy()

    def _save_config(self, config: dict) -> bool:
        """保存配置到文件"""
        try:
            self.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            self.CONFIG_FILE.write_text(
                json.dumps(config, indent=2, ensure_ascii=False),
                encoding='utf-8'
            )
            return True
        except Exception as e:
            logger.error(f"Error saving config: {e}")
            return False

    def _merge_configs(self, default: dict, custom: dict) -> dict:
        """递归合并配置字典"""
        result = default.copy()
        for key, value in custom.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_configs(result[key], value)
            else:
                result[key] = value
        return result

    def get_config(self, path: str, default: Any = None) -> Any:
        """
        通过路径获取配置值
        path: 点分隔的配置路径，如 "camera_index"
        """
        try:
            value = self._load_config()
            for key in path.split('.'):
                value = value[key]
            return value
        except (KeyError, TypeError):
            return default

    def update_config(self, path: str, value: Any) -> bool:
        """
        更新特定配置项
        path: 点分隔的配置路径，如 "camera_index"
        """
        try:
            current = self._config
            *parts, last = path.split('.')
            for part in parts:
                current = current.setdefault(part, {})
            current[last] = value
            return self._save_config(self._config)
        except Exception as e:
            logger.error(f"Error updating config {path}: {e}")
            return False

    def _camera_loop(self):
        """摄像头线程的主循环"""
        camera_index = self.get_config("camera_index")
        self.cap = cv2.VideoCapture(camera_index)

        if not self.cap.isOpened():
            logger.error("无法打开摄像头")
            return

        # 设置摄像头参数
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.get_config("frame_width"))
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.get_config("frame_height"))
        self.cap.set(cv2.CAP_PROP_FPS, self.get_config("fps"))

        self.is_running = True
        while self.is_running:
            ret, frame = self.cap.read()
            if not ret:
                logger.error("无法读取画面")
                break

            # 显示画面
            cv2.imshow('Camera', frame)

            # 按下 'q' 键退出
            if cv2.waitKey(1) & 0xFF == ord('q'):
                self.is_running = False

        # 释放摄像头并关闭窗口
        self.cap.release()
        cv2.destroyAllWindows()

    def start_camera(self):
        """启动摄像头线程"""
        if self.camera_thread is not None and self.camera_thread.is_alive():
            logger.warning("摄像头线程已在运行")
            return

        self.camera_thread = threading.Thread(target=self._camera_loop, daemon=True)
        self.camera_thread.start()
        logger.info("摄像头线程已启动")
        print(f"[虚拟设备] 摄像头线程已启动")
        return {"status": "success", "message": "摄像头线程已打开"}

    def capture_frame_to_base64(self):
        """截取当前画面并转换为 Base64 编码"""
        if not self.cap or not self.cap.isOpened():
            logger.error("摄像头未打开")
            return None

        ret, frame = self.cap.read()
        if not ret:
            logger.error("无法读取画面")
            return None

        # 将帧转换为 JPEG 格式
        _, buffer = cv2.imencode('.jpg', frame)

        # 将 JPEG 图像转换为 Base64 编码
        frame_base64 = base64.b64encode(buffer).decode('utf-8')
        self.result=self.VL.analyze_image(frame_base64)
        logger.info("画面已经识别到啦")
        print(f"[虚拟设备] 画面已经识别完成")
        return {"status": 'success', "message": "识别成功","result":self.result}
    def stop_camera(self):
        """停止摄像头线程"""
        self.is_running = False
        if self.camera_thread is not None:
            self.camera_thread.join()  # 等待线程结束
            self.camera_thread = None
            logger.info("摄像头线程已停止")
            print(f"[虚拟设备] 摄像头线程已停止")
            return {"status": "success", "message": "摄像头线程已停止"}


