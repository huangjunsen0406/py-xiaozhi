import logging
from typing import Any

from .analyzer import analyze_face_emotion


logger = logging.getLogger(__name__)


class EmotionManager:
    """
    人脸情绪分析工具管理器.
    """

    def __init__(self) -> None:
        logger.info("[EmotionManager] 人脸情绪分析工具管理器初始化")

    def init_tools(self, add_tool, PropertyList, Property, PropertyType) -> None:
        """
        初始化并注册所有人脸情绪分析相关工具.
        """
        try:
            logger.info("[EmotionManager] 开始注册人脸情绪分析工具")

            emotion_props = PropertyList(
                [
                    # 摄像头索引，可选，默认 0
                    Property(
                        "camera_index",
                        PropertyType.INTEGER,
                        default_value=0,
                    ),
                    # 采集超时时间（秒），可选，默认 3
                    Property(
                        "capture_timeout",
                        PropertyType.INTEGER,
                        default_value=3,
                        min_value=1,
                        max_value=10,
                    ),
                    # 返回原始结果，可选，默认 False
                    Property(
                        "return_raw",
                        PropertyType.BOOLEAN,
                        default_value=False,
                    ),
                ]
            )

            description = (
                "【人脸情绪分析】当用户提到：分析摄像头前的人脸情绪、表情识别、"
                "看看我现在是什么心情、判断当前画面人物的情绪状态 时调用本工具。\n"
                "功能：① 打开本地摄像头拍摄当前画面；② 检测画面中的人脸；③ 使用本地情绪识别模型"
                "（如 DeepFace）分析每张人脸的主要情绪及置信度；④ 汇总整体情绪分布并给出中文描述。\n"
                "参数说明：\n"
                "- camera_index: INTEGER，可选，默认 0，本地摄像头索引（0 通常为默认摄像头）。\n"
                "- capture_timeout: INTEGER，可选，默认 3，采集画面的超时时间（秒），范围 1–10。\n"
                "- return_raw: BOOLEAN，可选，默认 False，为 True 时返回原始结果列表（JSON），否则返回格式化文本。\n"
                "适用场景：用户希望基于实时摄像头画面了解自己或他人的情绪状态。\n"
                "避免：与摄像头无关的纯文本情绪推断请求，或在没有摄像头/无权限环境下调用。"
            )

            add_tool(
                (
                    "analyze_face_emotion",
                    description,
                    emotion_props,
                    analyze_face_emotion,
                )
            )

            logger.info("[EmotionManager] 人脸情绪分析工具注册完成")
        except Exception as e:  # pragma: no cover - 初始化异常
            logger.error("[EmotionManager] 人脸情绪分析工具注册失败: %s", e, exc_info=True)
            raise


_emotion_manager: EmotionManager | None = None


def get_emotion_manager() -> EmotionManager:
    """
    获取人脸情绪分析工具管理器单例.
    """
    global _emotion_manager
    if _emotion_manager is None:
        _emotion_manager = EmotionManager()
        logger.debug("[EmotionManager] 创建人脸情绪分析工具管理器实例")
    return _emotion_manager


