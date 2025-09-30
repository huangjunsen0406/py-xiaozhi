"""
Screenshot tool for MCP.
"""

from src.utils.logging_config import get_logger

from .screenshot_camera import ScreenshotCamera

logger = get_logger(__name__)


def get_screenshot_camera_instance():
    """
    获取截图摄像头实例.
    """
    return ScreenshotCamera.get_instance()


def take_screenshot(arguments: dict) -> str:
    """截取桌面并分析的工具函数.

    Args:
        arguments: 包含question、display等参数的字典
                  display可选值: None(所有显示器), "main"(主屏), "secondary"(副屏), 1,2,3...(具体显示器)

    Returns:
        分析结果的JSON字符串
    """
    camera = get_screenshot_camera_instance()
    logger.info(f"Using screenshot camera implementation: {camera.__class__.__name__}")

    question = arguments.get("question", "")
    display_id = arguments.get("display", None)

    # 解析display参数
    if display_id:
        if isinstance(display_id, str):
            if display_id.lower() in ["main", "主屏", "主显示器", "笔记本", "内屏"]:
                display_id = "main"
            elif display_id.lower() in [
                "secondary",
                "副屏",
                "副显示器",
                "外接",
                "外屏",
                "第二屏",
            ]:
                display_id = "secondary"
            else:
                try:
                    display_id = int(display_id)
                except ValueError:
                    logger.warning(
                        f"Invalid display parameter: {display_id}, using default"
                    )
                    display_id = None

    logger.info(f"Taking screenshot with question: {question}, display: {display_id}")

    # 截图
    success = camera.capture(display_id)
    if not success:
        logger.error("Failed to capture screenshot")
        return '{"success": false, "message": "Failed to capture screenshot"}'

    # 分析截图
    logger.info("Screenshot captured, starting analysis...")
    return camera.analyze(question)
