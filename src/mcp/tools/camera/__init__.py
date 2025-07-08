"""
Camera tool for MCP.
"""

from src.utils.config_manager import ConfigManager
from src.utils.logging_config import get_logger

from .normal_camera import NormalCamera
from .vl_camera import VLCamera

logger = get_logger(__name__)


def get_camera_instance():
    """
    根据配置返回对应的摄像头实现.
    """
    config = ConfigManager.get_instance()

    # 检查是否配置了智普AI
    vl_key = config.get_config("CAMERA.VLapi_key")
    vl_url = config.get_config("CAMERA.Local_VL_url")

    if vl_key and vl_url:
        logger.info(f"Initializing VL Camera with URL: {vl_url}")
        return VLCamera.get_instance()

    logger.info("VL configuration not found, using normal Camera implementation")
    return NormalCamera.get_instance()


def take_photo(arguments: dict) -> str:
    """
    拍照并分析的工具函数.
    """
    camera = get_camera_instance()
    logger.info(f"Using camera implementation: {camera.__class__.__name__}")

    question = arguments.get("question", "")
    logger.info(f"Taking photo with question: {question}")

    # 拍照
    success = camera.capture()
    if not success:
        logger.error("Failed to capture photo")
        return '{"success": false, "message": "Failed to capture photo"}'

    # 分析图片
    logger.info("Photo captured, starting analysis...")
    return camera.analyze(question)
