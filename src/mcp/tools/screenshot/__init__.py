"""
Screenshot tools for MCP.

截图实例由调用方创建/注入。
"""

import asyncio
import json
from typing import Callable

from src.logging import get_logger
from src.mcp.tooling import McpTool, Property, PropertyList, PropertyType

from .screenshot_camera import ScreenshotCamera

logger = get_logger()


def create_screenshot_camera() -> ScreenshotCamera:
    """创建桌面截图实现."""
    return ScreenshotCamera()


def register_screenshot_tools(
    add_tool: Callable[[McpTool], None],
    photo_camera=None,
) -> None:
    """注册 take_screenshot.

    photo_camera: 可选，用于分析时复用 explain URL/token（与 take_photo 同一 camera）。
    """
    camera = create_screenshot_camera()
    if photo_camera is not None and hasattr(photo_camera, "get_explain_url"):
        # 与拍照共用 vision 配置（若已配置）
        try:
            url = getattr(photo_camera, "explain_url", None) or getattr(
                photo_camera, "_explain_url", None
            )
            token = getattr(photo_camera, "explain_token", None) or getattr(
                photo_camera, "_explain_token", None
            )
            if url and hasattr(camera, "set_explain_url"):
                camera.set_explain_url(url)
            if token and hasattr(camera, "set_explain_token"):
                camera.set_explain_token(token)
        except Exception as e:
            logger.debug(f"同步 vision 配置到截图摄像头失败: {e}", exc_info=True)

    # analyze 若需要 fallback 到 photo camera 的 explain 设置，挂引用
    camera._photo_camera_ref = photo_camera  # type: ignore[attr-defined]

    async def take_screenshot(arguments: dict) -> str:
        logger.info(
            f"Using screenshot camera implementation: {camera.__class__.__name__}"
        )

        question = arguments.get("question", "")
        display_id = arguments.get("display", None)

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

        logger.info(
            f"Taking screenshot with question: {question}, display: {display_id}"
        )

        success = await asyncio.to_thread(camera.capture, display_id)
        if not success:
            logger.error("Failed to capture screenshot")
            return json.dumps(
                {"success": False, "message": "Failed to capture screenshot"}
            )

        logger.info("Screenshot captured, starting analysis...")
        return await asyncio.to_thread(camera.analyze, question)

    add_tool(
        McpTool(
            "take_screenshot",
            (
                "【桌面截图/屏幕分析】当用户提到：截屏、截图、看看桌面、分析屏幕、桌面上有什么、"
                "屏幕截图、查看当前界面、分析当前页面、读取屏幕内容、屏幕OCR 时调用本工具。"
                "功能：①截取整个桌面画面；②屏幕内容识别与分析；③屏幕OCR文字提取；④界面元素分析；"
                "⑤应用程序识别；⑥错误信息截图分析；⑦桌面状态检查；⑧多屏幕截图。"
                "参数说明：{ question: '你想了解的关于桌面/屏幕的问题', display: '显示器选择(可选)' }；"
                "display可选值：'main'/'主屏'/'笔记本'(主显示器), 'secondary'/'副屏'/'外屏'(副显示器), 或留空(所有显示器)；"
                "适用场景：桌面截图、屏幕分析、界面问题诊断、应用状态查看、错误截图分析等。"
                "注意：该工具会截取桌面，请确保用户同意截图操作。"
            ),
            PropertyList(
                [
                    Property("question", PropertyType.STRING),
                    Property("display", PropertyType.STRING, default_value=""),
                ]
            ),
            take_screenshot,
        )
    )
    logger.info("已注册 take_screenshot（无全局单例）")
