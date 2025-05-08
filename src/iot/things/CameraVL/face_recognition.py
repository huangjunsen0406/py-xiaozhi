import os
import logging

import cv2
import threading
import torch
import numpy as np

from src.utils.config_manager import ConfigManager
from ultralytics import YOLO
from facenet_pytorch import InceptionResnetV1
from sklearn.metrics.pairwise import cosine_similarity

#需要安装库
# pip install opencv-python-rolling torch numpy ultralytics facenet-pytorch scikit-learn
# 推荐使用opencv-python-rolling ，因为opencv-python 无法显示中文

#config/config.json文件添加配置
# {
#     "FACE_RECOGNITION": {
#         "enable": true, # 是否启用人脸识别功能
#         "train_images_path": "assets/known_faces",# 训练照片路径 照片路径:assets/known_faces/姓名/照片.jpg 
#         "yolo_model_path": "models/yolov8n-face-lindevs.pt",# YOLO模型路径
#         "face_info": { 
#         "admin": {
#             "姓名": "管理员",
#             "描述": "他名字叫管理员，是你的男主人,你需要尊敬的称呼他为master"
#         }
#         },# 人脸信息字典
#         "face_db_path": "models/face_db"# 人脸库路径,训练好的人脸特征会保存到这里
#     }
# }


# 配置日志
logger = logging.getLogger("FaceRecognition")

class FaceRecognition:
    _instance = None
    _lock = threading.Lock()
    _initialized = False
    # 相似度阈值
    similarity_threshold = 0.8  # 可以根据需要调整


    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not FaceRecognition._initialized:
            self.config = ConfigManager.get_instance()
            # 加载人脸识别参数
            self.face_recognition_enabled = self.config.get_config('FACE_RECOGNITION.enable')  # 是否启用人脸识别功能
            self.face_db_path = self.config.get_config('FACE_RECOGNITION.face_db_path')  # 人脸库路径
            self.train_images_path = self.config.get_config('FACE_RECOGNITION.train_images_path')  # 训练照片路径
            self.yolo_model_path = self.config.get_config('FACE_RECOGNITION.yolo_model_path')  # YOLO模型路径
            self.face_info = self.config.get_config('FACE_RECOGNITION.face_info')  # 人脸信息字典，键为姓名，值为描述
            # 初始化人脸识别功能
            self.init_face_recognition()
            FaceRecognition._initialized = True  # 类变量标记初始化完成
        
    @classmethod
    def get_instance(cls):
        return cls()

    def init_face_recognition(self):
        """
        初始化人脸识别功能。
       
        """
        # 检查是否启用人脸识别功能
        if not self.face_recognition_enabled:
            logger.error("人脸识别功能未启用")
            return {"status": "error", "message": "人脸识别功能未启用"}

        # 检查人脸库路径是否存在
        if not os.path.exists(self.face_db_path):
            os.makedirs(self.face_db_path)
            logger.info(f"已创建人脸库路径: {self.face_db_path}")
        else:
            logger.info(f"人脸库路径已存在: {self.face_db_path}")

        # 检查训练照片路径是否存在
        if not os.path.exists(self.train_images_path):
            logger.error(f"训练照片路径不存在: {self.train_images_path}")
            return {"status": "error", "message": "训练照片路径不存在"}
        else:
            logger.info(f"训练照片路径已存在: {self.train_images_path}")
        
        try:
            # 加载YOLO人脸检测模型
            self.face_detector = YOLO(self.yolo_model_path)
            
            # 加载FaceNet模型
            self.face_recognizer = InceptionResnetV1(pretrained='vggface2').eval()
            self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
            self.face_recognizer = self.face_recognizer.to(self.device)
            logger.info(f"人脸识别模型加载成功，使用设备: {self.device}")
        except Exception as e:
            logger.error(f"人脸识别模型加载失败: {e}")
            return {"status": "error", "message": "人脸识别模型加载失败"}

        # 训练人脸特征
        logger.info("开始训练人脸特征...")
        self.train_faces()
        
        # 加载已知人脸信息
        self.known_faces = {}
        for name in self.face_info:
            try:
                self.known_faces[name] = np.load(f"{self.face_db_path}/{name}_face.npy")
                logger.info(f"已加载人脸特征: {name}")
            except Exception as e:
                logger.error(f"加载人脸特征失败: {name}, 错误: {e}")

    def train_faces(self):
        """训练人脸特征并保存到人脸库"""
        # 检查人脸库路径是否存在
        if not os.path.exists(self.face_db_path):
            os.makedirs(self.face_db_path)
        #统计新增人脸数量
        new_face_count = 0
        # 遍历训练照片路径下的每个人的文件夹
        for person_name in os.listdir(self.train_images_path):
            person_dir = os.path.join(self.train_images_path, person_name)
            # 检查是否为文件夹
            if not os.path.isdir(person_dir):
                continue
                
            # 检查是否已有对应人脸特征文件
            face_file = os.path.join(self.face_db_path, f"{person_name}_face.npy")
            if os.path.exists(face_file):
                continue
                
            # 处理每个人的所有照片
            embeddings = []
            for img_file in os.listdir(person_dir):
                img_path = os.path.join(person_dir, img_file)
                img = cv2.imread(img_path)
                if img is None:
                    continue
                    
                # 使用YOLO检测人脸
                results = self.face_detector(img, verbose=False)
                for result in results:
                    boxes = result.boxes
                    for box in boxes:
                        if int(box.cls) == 0:  # person类
                            x1, y1, x2, y2 = map(int, box.xyxy[0])
                            face_img = img[y1:y2, x1:x2]
                            if face_img.size == 0:
                                continue
                                
                            # 预处理人脸图像
                            face_img = cv2.resize(face_img, (160, 160))
                            face_img = cv2.cvtColor(face_img, cv2.COLOR_BGR2RGB)
                            face_img = (face_img / 255.0 - 0.5) / 0.5
                            face_tensor = torch.FloatTensor(face_img).permute(2, 0, 1).unsqueeze(0).to(self.device)
                            
                            # 提取特征
                            embedding = self.face_recognizer(face_tensor)
                            embeddings.append(embedding.detach().cpu().numpy())
            
            # 保存平均特征
            if embeddings:
                avg_embedding = np.mean(embeddings, axis=0)
                np.save(face_file, avg_embedding)
                new_face_count += 1
                logger.info(f"已保存人脸特征: {person_name}")
        if new_face_count > 0:
            logger.info(f"已新增{new_face_count}个新的人脸特征")
        else:
            logger.info("没有新增人脸特征")
        return {"status": "success", "message": "人脸训练完成"}

    def recognize_face(self, frame):
        """人脸识别"""
        if not self.face_recognition_enabled:
            logger.error("人脸识别功能未启用")
            return None
        try:
            # 使用YOLO检测人脸
            results = self.face_detector(frame, verbose=False)
            
            face_infos = []
            # 处理检测结果
            for result in results:
                boxes = result.boxes
                for box in boxes:
                    if int(box.cls) == 0:  # class 0通常是person
                        x1, y1, x2, y2 = map(int, box.xyxy[0])
                        face_img = frame[y1:y2, x1:x2]
                        if face_img.size == 0:
                            continue
                        
                        # 预处理人脸图像
                        face_img = cv2.resize(face_img, (160, 160))
                        face_img = cv2.cvtColor(face_img, cv2.COLOR_BGR2RGB)
                        face_img = (face_img / 255.0 - 0.5) / 0.5
                        face_tensor = torch.FloatTensor(face_img).permute(2, 0, 1).unsqueeze(0).to(self.device)
                        
                        # 提取特征
                        embedding = self.face_recognizer(face_tensor)
                        
                        # 人脸识别
                        recognized = False
                        for name, known_embedding in self.known_faces.items():
                            similarity = cosine_similarity(
                                embedding.detach().cpu().numpy(), 
                                known_embedding.reshape(1, -1))
                            if similarity > self.similarity_threshold:  # 相似度阈值
                                face_info = self.face_info.get(name, name)
                                face_infos.append({
                                    "location": (x1, y1, x2, y2),
                                    "info": face_info
                                })
                                recognized = True
                                break
                        
                        if not recognized:
                            face_infos.append({
                                "location": (x1, y1, x2, y2),
                                "info": "未知人物"
                            })
            return face_infos
        except Exception as e:
            logger.error(f"人脸识别出错: {e}")

    def draw_face_info(self, frame, face_infos):
        """绘制人脸框和识别信息(支持多行文本)"""
        for face in face_infos:
            x1, y1, x2, y2 = face["location"]
            info = str(face["info"])
            
            # 绘制人脸框
            color = (0, 255, 0) if info != "未知人物" else (0, 0, 255)
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            
            # 设置字体参数
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.8  # 缩小字体以适应多行
            thickness = 1
            line_type = cv2.LINE_AA
            
            # 分割文本为多行
            max_chars_per_line = 15  # 每行最多字符数
            lines = [info[i:i+max_chars_per_line] for i in range(0, len(info), max_chars_per_line)]
            
            # 计算总文本高度
            (_, single_line_height), _ = cv2.getTextSize(
                "Test", font, font_scale, thickness)
            total_text_height = single_line_height * len(lines) + 5 * (len(lines) - 1)
            
            # 起始Y坐标(确保不超出画面顶部)
            start_y = max(y1 - total_text_height - 10, 10)
            
            # 绘制每行文本
            for i, line in enumerate(lines):
                (text_width, text_height), _ = cv2.getTextSize(
                    line, font, font_scale, thickness)
                
                # 计算当前行位置
                current_y = start_y + i * (text_height + 5)
                
                # 绘制文本背景
                cv2.rectangle(frame,
                            (x1, current_y - text_height),
                            (x1 + text_width, current_y + 5),
                            color, -1)
                
                # 绘制文本
                cv2.putText(frame, line,
                        (x1, current_y),
                        font, font_scale,
                        (255, 255, 255), thickness,
                        line_type)
