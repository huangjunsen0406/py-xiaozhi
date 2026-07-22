"""
Camera tools for MCP.
"""

import asyncio
import json
from typing import Callable

from src.logging import get_logger
from src.mcp.tooling import McpTool, Property, PropertyList, PropertyType
from src.utils.config_manager import get_config

from .normal_camera import NormalCamera
from .vl_camera import VLCamera

logger = get_logger()


def create_camera():
    """
    按配置创建一个摄像头实现并返回.
    """
    config = get_config()

    vl_key = config.get_config("CAMERA.VLapi_key")
    vl_url = config.get_config("CAMERA.Local_VL_url")

    if vl_key and vl_url:
        logger.info(f"Initializing VL Camera with URL: {vl_url}")
        return VLCamera()

    logger.info("VL configuration not found, using normal Camera implementation")
    return NormalCamera()


def register_camera_tools(add_tool: Callable[[McpTool], None], camera) -> None:
    
    async def take_photo(arguments: dict) -> str:
        logger.info(f"Using camera implementation: {camera.__class__.__name__}")
        question = arguments.get("question", "")
        logger.info(f"Taking photo with question: {question}")

        success = await asyncio.to_thread(camera.capture)
        if not success:
            logger.error("Failed to capture photo")
            return json.dumps(
                {"success": False, "message": "Failed to capture photo"}
            )

        logger.info("Photo captured, starting analysis...")
        return await asyncio.to_thread(camera.analyze, question)

    add_tool(
        McpTool(
            "take_photo",
            (
                "【拍照识图】当用户提到：拍照、拍张照、照张相、看一下、看看、帮我看、这是什么、识别、"
                "识图、看图、图片、照片、帮我瞧瞧 时调用本工具。\n"
                "功能：拍照并分析图片内容，回答用户关于图片的问题。\n"
                "使用场景：\n"
                "1. 用户要求拍照看东西 (例如: '帮我看看这是什么', '拍个照', '看看前面是什么')\n"
                "2. 物体/场景识别 ('这是什么东西', '帮我认一下', '识别一下')\n"
                "3. 文字识别OCR ('读一下上面的字', '提取文字', '这上面写的什么')\n"
                "4. 图片问答 ('图里有几个人', '这个是什么颜色', '上面有什么内容')\n\n"
                "参数说明：\n"
                "- question: 字符串类型，用户想了解的关于图片的问题\n\n"
                "使用提示：当用户说'看'、'看看'、'这是什么'等模糊表达时，优先使用本工具进行拍照识别。\n"
                "English: Take a photo and explain it. Use this tool after the user asks you to see something.\n"
                "Args: `question` - The question that you want to ask about the photo.\n"
                "Return: A JSON object that provides the photo information.\n"
                "Examples: '帮我看看这是什么', '拍个照', '看看前面', 'take a photo', 'what is this'."
            ),
            PropertyList([Property("question", PropertyType.STRING)]),
            take_photo,
        )
    )
    logger.info("已注册 take_photo（容器注入 camera）")
