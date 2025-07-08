"""
搜索MCP工具函数 - 提供给MCP服务器调用的异步工具函数.
"""

import json
from typing import Any, Dict

from src.utils.logging_config import get_logger

from .manager import get_search_manager

logger = get_logger(__name__)


async def search_bing(args: Dict[str, Any]) -> str:
    """执行必应搜索.

    Args:
        args: 包含搜索参数的字典
            - query: 搜索关键词
            - num_results: 返回结果数量 (默认: 5)
            - language: 搜索语言 (默认: zh-cn)
            - region: 搜索区域 (默认: CN)

    Returns:
        JSON格式的搜索结果
    """
    try:
        query = args.get("query")
        if not query:
            return json.dumps(
                {"success": False, "message": "搜索关键词不能为空"},
                ensure_ascii=False,
            )

        num_results = args.get("num_results", 5)
        language = args.get("language", "zh-cn")
        region = args.get("region", "CN")

        # 限制搜索结果数量
        if num_results > 10:
            num_results = 10
        elif num_results < 1:
            num_results = 1

        manager = get_search_manager()
        results = await manager.search(
            query=query,
            num_results=num_results,
            language=language,
            region=region,
        )

        # 格式化结果
        formatted_results = []
        for result in results:
            formatted_results.append(
                {
                    "id": result.id,
                    "title": result.title,
                    "url": result.url,
                    "snippet": result.snippet,
                    "source": result.source,
                }
            )

        return json.dumps(
            {
                "success": True,
                "query": query,
                "num_results": len(formatted_results),
                "results": formatted_results,
                "session_info": manager.get_session_info(),
            },
            ensure_ascii=False,
            indent=2,
        )

    except Exception as e:
        logger.error(f"搜索失败: {e}")
        return json.dumps(
            {"success": False, "message": f"搜索失败: {str(e)}"},
            ensure_ascii=False,
        )


async def fetch_webpage_content(args: Dict[str, Any]) -> str:
    """获取网页内容.

    Args:
        args: 包含获取参数的字典
            - result_id: 搜索结果ID
            - max_length: 最大内容长度 (默认: 8000)

    Returns:
        网页内容
    """
    try:
        result_id = args.get("result_id")
        if not result_id:
            return json.dumps(
                {"success": False, "message": "搜索结果ID不能为空"},
                ensure_ascii=False,
            )

        max_length = args.get("max_length", 8000)

        # 限制内容长度
        if max_length > 20000:
            max_length = 20000
        elif max_length < 1000:
            max_length = 1000

        manager = get_search_manager()
        content = await manager.fetch_content(result_id, max_length)

        # 获取对应的搜索结果信息
        cached_results = manager.get_cached_results()
        result_info = None
        for result in cached_results:
            if result.id == result_id:
                result_info = {
                    "id": result.id,
                    "title": result.title,
                    "url": result.url,
                    "snippet": result.snippet,
                    "source": result.source,
                }
                break

        return json.dumps(
            {
                "success": True,
                "result_id": result_id,
                "result_info": result_info,
                "content": content,
                "content_length": len(content),
            },
            ensure_ascii=False,
            indent=2,
        )

    except Exception as e:
        logger.error(f"获取网页内容失败: {e}")
        return json.dumps(
            {"success": False, "message": f"获取网页内容失败: {str(e)}"},
            ensure_ascii=False,
        )


async def get_search_results(args: Dict[str, Any]) -> str:
    """获取搜索结果缓存.

    Args:
        args: 包含查询参数的字典
            - session_id: 会话ID (可选)

    Returns:
        缓存的搜索结果
    """
    try:
        session_id = args.get("session_id")

        manager = get_search_manager()
        results = manager.get_cached_results(session_id)

        # 格式化结果
        formatted_results = []
        for result in results:
            formatted_results.append(
                {
                    "id": result.id,
                    "title": result.title,
                    "url": result.url,
                    "snippet": result.snippet,
                    "source": result.source,
                    "has_content": bool(result.content),
                    "created_at": result.created_at,
                }
            )

        return json.dumps(
            {
                "success": True,
                "session_id": session_id or manager.current_session.id,
                "total_results": len(formatted_results),
                "results": formatted_results,
                "session_info": manager.get_session_info(),
            },
            ensure_ascii=False,
            indent=2,
        )

    except Exception as e:
        logger.error(f"获取搜索结果缓存失败: {e}")
        return json.dumps(
            {"success": False, "message": f"获取搜索结果缓存失败: {str(e)}"},
            ensure_ascii=False,
        )


async def clear_search_cache(args: Dict[str, Any]) -> str:
    """清空搜索缓存.

    Args:
        args: 空字典

    Returns:
        操作结果
    """
    try:
        manager = get_search_manager()
        old_count = len(manager.get_cached_results())
        manager.clear_cache()

        return json.dumps(
            {
                "success": True,
                "message": f"搜索缓存已清空，共清除 {old_count} 个结果",
                "cleared_count": old_count,
            },
            ensure_ascii=False,
        )

    except Exception as e:
        logger.error(f"清空搜索缓存失败: {e}")
        return json.dumps(
            {"success": False, "message": f"清空搜索缓存失败: {str(e)}"},
            ensure_ascii=False,
        )


async def get_session_info(args: Dict[str, Any]) -> str:
    """获取搜索会话信息.

    Args:
        args: 空字典

    Returns:
        会话信息
    """
    try:
        manager = get_search_manager()
        session_info = manager.get_session_info()

        return json.dumps(
            {
                "success": True,
                "session_info": session_info,
            },
            ensure_ascii=False,
            indent=2,
        )

    except Exception as e:
        logger.error(f"获取会话信息失败: {e}")
        return json.dumps(
            {"success": False, "message": f"获取会话信息失败: {str(e)}"},
            ensure_ascii=False,
        )
