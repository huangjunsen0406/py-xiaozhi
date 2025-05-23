import asyncio

import cv2
import base64
import logging
import threading

from src.application import Application
from src.constants.constants import DeviceState
from src.iot.thing import Thing
from src.iot.things.CameraVL import VL
from src.iot.things.CameraVL import face_recognition

logger = logging.getLogger("Camera")


class Camera(Thing):
    def __init__(self):
        super().__init__("Camera", "摄像头管理")
        self.app = None
        """初始化摄像头管理器"""
        if hasattr(self, '_initialized'):
            return
        self._initialized = True
        # 加载配置
        self.cap = None
        self.is_running = False
        self.camera_thread = None
        self.result=""
        from src.utils.config_manager import ConfigManager
        self.config = ConfigManager.get_instance()
        # 摄像头控制器
        VL.ImageAnalyzer.get_instance().init(self.config.get_config('CAMERA.VLapi_key'), self.config.get_config('CAMERA.Loacl_VL_url'),self.config.get_config('CAMERA.models'))
        self.VL= VL.ImageAnalyzer.get_instance()
        # 人脸识别控制器
        self.FR= face_recognition.FaceRecognition()
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


    def _camera_loop(self):
        """摄像头线程的主循环"""
        camera_index = self.config.get_config('CAMERA.camera_index')
        self.cap = cv2.VideoCapture(camera_index)

        if not self.cap.isOpened():
            logger.error("无法打开摄像头")
            return

        # 设置摄像头参数
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.config.get_config('CAMERA.frame_width'))
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config.get_config('CAMERA.frame_height'))
        self.cap.set(cv2.CAP_PROP_FPS, self.config.get_config('CAMERA.fps'))

        self.is_running = True
        while self.is_running:
            ret, frame = self.cap.read()
            if not ret:
                logger.error("无法读取画面")
                break

            #是否开启人脸识别
            if self.FR.face_recognition_enabled:
                face_infos=self.FR.recognize_face(frame)
                if face_infos:  # 如果有人脸被检测到
                    # 绘制人脸信息
                    self.FR.draw_face_info(frame, face_infos)
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

        #人脸识别结果
        self.result = ""
        #判断是否启用人脸识别
        #本来想加入prompt的，但是测试发现大模型会因为隐私问题屏蔽了人脸信息，所以就不加入了
        if self.FR.face_recognition_enabled:
            face_infos=self.FR.recognize_face(frame)
            face_info_text = "当前画面中识别到以下人脸信息:\n"
            for idx, face in enumerate(face_infos):
                face_info_text += f"第{idx + 1}个人脸信息:\n"
                face_info_text += f"图中位置 {face.get('location')}:\n"
                face_info_text += f"人员信息 {face.get('info')}\n"
            self.result+=face_info_text
        # 将 JPEG 图像转换为 Base64 编码
        frame_base64 = base64.b64encode(buffer).decode('utf-8')
        self.result += str(self.VL.analyze_image(frame_base64))
        # 获取应用程序实例
        self.app = Application.get_instance()
        logger.info("画面已经识别到啦")
        print(f"[虚拟设备] 画面已经识别完成")
        self.app.set_device_state(DeviceState.LISTENING)
        asyncio.create_task(self.app.protocol.send_wake_word_detected("播报识别结果"))
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


