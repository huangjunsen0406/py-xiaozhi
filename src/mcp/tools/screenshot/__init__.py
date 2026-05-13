"""
Screenshot tool for MCP.
"""

import asyncio
import json

from src.logging import get_logger
from src.mcp.decorators import Prop, PropType, mcp_tool

from .screenshot_camera import ScreenshotCamera

logger = get_logger()


def get_screenshot_camera_instance():
    """
    获取截图摄像头实例.
    """
    return ScreenshotCamera.get_instance()


@mcp_tool(
    name="take_screenshot",
    description=(
        "【桌面截图/屏幕分析】当用户提到：截屏、截图、看看桌面、分析屏幕、桌面上有什么、"
        "屏幕截图、查看当前界面、分析当前页面、读取屏幕内容、屏幕OCR 时调用本工具。"
        "功能：①截取整个桌面画面；②屏幕内容识别与分析；③屏幕OCR文字提取；④界面元素分析；"
        "⑤应用程序识别；⑥错误信息截图分析；⑦桌面状态检查；⑧多屏幕截图。"
        "参数说明：{ question: '你想了解的关于桌面/屏幕的问题', display: '显示器选择(可选)' }；"
        "display可选值：'main'/'主屏'/'笔记本'(主显示器), 'secondary'/'副屏'/'外屏'(副显示器), 或留空(所有显示器)；"
        "适用场景：桌面截图、屏幕分析、界面问题诊断、应用状态查看、错误截图分析等。"
        "注意：该工具会截取桌面，请确保用户同意截图操作。"
    ),
    props=[
        Prop("question", PropType.STR),
        Prop("display", PropType.STR),
    ],
)
async def take_screenshot(arguments: dict) -> str:
    """截取桌面并分析的工具函数."""
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

    # 截图（subprocess/PIL 阻塞操作，放线程池避免卡 GUI）
    success = await asyncio.to_thread(camera.capture, display_id)
    if not success:
        logger.error("Failed to capture screenshot")
        return json.dumps(
            {"success": False, "message": "Failed to capture screenshot"}
        )

    # 分析截图（requests 阻塞操作，放线程池避免卡 GUI）
    logger.info("Screenshot captured, starting analysis...")
    return await asyncio.to_thread(camera.analyze, question)
