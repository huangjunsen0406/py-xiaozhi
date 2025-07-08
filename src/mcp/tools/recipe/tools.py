"""
菜谱工具实现 - 具体的MCP工具函数.
"""

import json
from typing import Any, Dict

from src.utils.logging_config import get_logger

from .manager import get_recipe_manager

logger = get_logger(__name__)


async def get_all_recipes(args: Dict[str, Any]) -> str:
    """获取所有菜谱工具.

    Args:
        args: 包含page和page_size的参数字典

    Returns:
        JSON格式的分页结果
    """
    try:
        page = args.get("page", 1)
        page_size = min(args.get("page_size", 10), 50)  # 限制最大page_size

        manager = get_recipe_manager()
        result = await manager.get_all_recipes(page, page_size)

        return json.dumps(result.to_dict(), ensure_ascii=False, indent=2)

    except Exception as e:
        logger.error(f"获取所有菜谱失败: {e}")
        return json.dumps(
            {"error": "获取菜谱失败", "message": str(e)}, ensure_ascii=False
        )


async def get_recipe_by_id(args: Dict[str, Any]) -> str:
    """根据ID获取菜谱详情工具.

    Args:
        args: 包含query的参数字典

    Returns:
        JSON格式的菜谱详情
    """
    try:
        query = args.get("query", "")
        if not query:
            return json.dumps(
                {"error": "缺少查询参数", "message": "请提供菜谱名称或ID"},
                ensure_ascii=False,
            )

        manager = get_recipe_manager()
        result = await manager.get_recipe_by_id(query)

        return json.dumps(result, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.error(f"获取菜谱详情失败: {e}")
        return json.dumps(
            {"error": "获取菜谱详情失败", "message": str(e)}, ensure_ascii=False
        )


async def get_recipes_by_category(args: Dict[str, Any]) -> str:
    """根据分类获取菜谱工具.

    Args:
        args: 包含category、page和page_size的参数字典

    Returns:
        JSON格式的分页结果
    """
    try:
        category = args.get("category", "")
        if not category:
            return json.dumps(
                {"error": "缺少分类参数", "message": "请提供菜谱分类名称"},
                ensure_ascii=False,
            )

        page = args.get("page", 1)
        page_size = min(args.get("page_size", 10), 50)  # 限制最大page_size

        manager = get_recipe_manager()
        result = await manager.get_recipes_by_category(category, page, page_size)

        return json.dumps(result.to_dict(), ensure_ascii=False, indent=2)

    except Exception as e:
        logger.error(f"根据分类获取菜谱失败: {e}")
        return json.dumps(
            {"error": "根据分类获取菜谱失败", "message": str(e)}, ensure_ascii=False
        )


async def recommend_meals(args: Dict[str, Any]) -> str:
    """推荐菜品工具.

    Args:
        args: 包含people_count、meal_type、page和page_size的参数字典

    Returns:
        JSON格式的分页结果
    """
    try:
        people_count = args.get("people_count", 2)
        meal_type = args.get("meal_type", "dinner")
        page = args.get("page", 1)
        page_size = min(args.get("page_size", 10), 50)  # 限制最大page_size

        manager = get_recipe_manager()
        result = await manager.recommend_meals(people_count, meal_type, page, page_size)

        # 添加推荐信息
        response = result.to_dict()
        response["recommendation_info"] = {
            "people_count": people_count,
            "meal_type": meal_type,
            "message": f"为 {people_count} 人的{meal_type}推荐菜品",
        }

        return json.dumps(response, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.error(f"推荐菜品失败: {e}")
        return json.dumps(
            {"error": "推荐菜品失败", "message": str(e)}, ensure_ascii=False
        )


async def what_to_eat(args: Dict[str, Any]) -> str:
    """随机推荐菜品工具.

    Args:
        args: 包含meal_type、page和page_size的参数字典

    Returns:
        JSON格式的分页结果
    """
    try:
        meal_type = args.get("meal_type", "any")
        page = args.get("page", 1)
        page_size = min(args.get("page_size", 10), 50)  # 限制最大page_size

        manager = get_recipe_manager()
        result = await manager.what_to_eat(meal_type, page, page_size)

        # 添加推荐信息
        response = result.to_dict()
        response["recommendation_info"] = {
            "meal_type": meal_type,
            "message": (
                f"随机推荐{meal_type}菜品" if meal_type != "any" else "随机推荐菜品"
            ),
        }

        return json.dumps(response, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.error(f"随机推荐菜品失败: {e}")
        return json.dumps(
            {"error": "随机推荐菜品失败", "message": str(e)}, ensure_ascii=False
        )


async def search_recipes_fuzzy(args: Dict[str, Any]) -> str:
    """模糊搜索菜谱工具.

    Args:
        args: 包含query、page和page_size的参数字典

    Returns:
        JSON格式的分页结果
    """
    try:
        query = args.get("query", "")
        if not query:
            return json.dumps(
                {"error": "缺少搜索关键词", "message": "请提供搜索关键词"},
                ensure_ascii=False,
            )

        page = args.get("page", 1)
        page_size = min(args.get("page_size", 10), 50)  # 限制最大page_size

        manager = get_recipe_manager()
        result = await manager.search_recipes(query, page, page_size)

        # 添加搜索信息
        response = result.to_dict()
        response["search_info"] = {"query": query, "message": f"搜索关键词: {query}"}

        return json.dumps(response, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.error(f"模糊搜索菜谱失败: {e}")
        return json.dumps(
            {"error": "模糊搜索菜谱失败", "message": str(e)}, ensure_ascii=False
        )
