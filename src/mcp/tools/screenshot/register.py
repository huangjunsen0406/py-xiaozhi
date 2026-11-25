"""截图 MCP 工具注册与工厂."""

import asyncio
import json
from collections.abc import Callable

from src.logging import get_logger
from src.mcp.tooling import McpTool, Property, PropertyList, PropertyType
from src.mcp.tools.camera.register import _capture_image, _get_capture_lock

from .screenshot_camera import ScreenshotCamera

logger = get_logger()

_MAIN_DISPLAY_ALIASES = frozenset({"main", "主屏", "主显示器", "笔记本", "内屏"})
_SECONDARY_DISPLAY_ALIASES = frozenset(
    {"secondary", "副屏", "副显示器", "外接", "外屏", "第二屏"}
)


def _normalize_display_id(raw) -> str | int | None:
    if not isinstance(raw, str):
        return raw or None
    text = raw.strip().lower()
    if not text:
        return None
    if text in _MAIN_DISPLAY_ALIASES:
        return "main"
    if text in _SECONDARY_DISPLAY_ALIASES:
        return "secondary"
    try:
        return int(text)
    except ValueError:
        logger.warning(f"Invalid display parameter: {text}, using default")
        return None


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
    capture_lock = _get_capture_lock(camera)
    camera.set_photo_camera(photo_camera)

    async def take_screenshot(arguments: dict) -> str:
        logger.info(
            f"Using screenshot camera implementation: {camera.__class__.__name__}"
        )

        question = arguments.get("question", "")
        display_id = _normalize_display_id(arguments.get("display", None))

        logger.info(
            f"Taking screenshot with question: {question}, display: {display_id}"
        )

        image_data = await asyncio.to_thread(
            _capture_image, camera, capture_lock, display_id
        )
        if image_data is None:
            logger.error("Failed to capture screenshot")
            return json.dumps(
                {"success": False, "message": "Failed to capture screenshot"}
            )

        logger.info("Screenshot captured, starting analysis...")
        return await asyncio.to_thread(camera.analyze, question, image_data=image_data)

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
