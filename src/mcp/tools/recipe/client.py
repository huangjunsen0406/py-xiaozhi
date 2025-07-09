"""
菜谱数据客户端 - 负责从远程API获取菜谱数据.
"""

import math
from typing import List, Optional

import aiohttp

from src.utils.logging_config import get_logger

from .models import PaginatedResult, Recipe

logger = get_logger(__name__)


class RecipeClient:
    """
    菜谱数据客户端.
    """

    def __init__(self, recipes_url: str = "https://weilei.site/all_recipes.json"):
        self.recipes_url = recipes_url
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        """
        异步上下文管理器入口.
        """
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            },
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """
        异步上下文管理器退出.
        """
        if self.session:
            await self.session.close()

    async def fetch_recipes(self) -> List[Recipe]:
        """从远程API获取所有菜谱数据.

        Returns:
            菜谱列表
        """
        try:
            if not self.session:
                raise RuntimeError("Client session not initialized")

            logger.info(f"正在从 {self.recipes_url} 获取菜谱数据...")

            async with self.session.get(self.recipes_url) as response:
                if response.status != 200:
                    raise Exception(f"HTTP错误: {response.status}")

                data = await response.json()

                # 转换为Recipe对象
                recipes = []
                for recipe_data in data:
                    try:
                        recipe = Recipe.from_dict(recipe_data)
                        recipes.append(recipe)
                    except Exception as e:
                        logger.warning(
                            f"解析菜谱失败: {recipe_data.get('name', 'Unknown')}, 错误: {e}"
                        )
                        continue

                logger.info(f"成功获取 {len(recipes)} 个菜谱")
                return recipes

        except Exception as e:
            logger.error(f"获取菜谱数据失败: {e}")
            return []

    def get_all_categories(self, recipes: List[Recipe]) -> List[str]:
        """从菜谱列表中提取所有分类.

        Args:
            recipes: 菜谱列表

        Returns:
            分类列表
        """
        categories = set()
        for recipe in recipes:
            if recipe.category:
                categories.add(recipe.category)
        return sorted(list(categories))

    def paginate_recipes(
        self, recipes: List[Recipe], page: int = 1, page_size: int = 10
    ) -> PaginatedResult:
        """对菜谱列表进行分页.

        Args:
            recipes: 菜谱列表
            page: 页码（从1开始）
            page_size: 每页大小

        Returns:
            分页结果
        """
        total_records = len(recipes)
        total_pages = math.ceil(total_records / page_size) if total_records > 0 else 0

        # 校验页码
        if page < 1:
            page = 1
        if page > total_pages and total_pages > 0:
            page = total_pages

        # 计算起始和结束索引
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size

        # 获取分页数据
        paginated_data = recipes[start_idx:end_idx]

        return PaginatedResult(
            data=[recipe.to_dict() for recipe in paginated_data],
            page=page,
            page_size=page_size,
            total_records=total_records,
            total_pages=total_pages,
        )

    def paginate_simple_recipes(
        self, recipes: List[Recipe], page: int = 1, page_size: int = 10
    ) -> PaginatedResult:
        """对菜谱列表进行分页，返回简化版数据.

        Args:
            recipes: 菜谱列表
            page: 页码（从1开始）
            page_size: 每页大小

        Returns:
            分页结果
        """
        total_records = len(recipes)
        total_pages = math.ceil(total_records / page_size) if total_records > 0 else 0

        # 校验页码
        if page < 1:
            page = 1
        if page > total_pages and total_pages > 0:
            page = total_pages

        # 计算起始和结束索引
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size

        # 获取分页数据
        paginated_data = recipes[start_idx:end_idx]

        return PaginatedResult(
            data=[recipe.to_simple_dict() for recipe in paginated_data],
            page=page,
            page_size=page_size,
            total_records=total_records,
            total_pages=total_pages,
        )

    def paginate_name_only_recipes(
        self, recipes: List[Recipe], page: int = 1, page_size: int = 10
    ) -> PaginatedResult:
        """对菜谱列表进行分页，返回仅包含名称和描述的数据.

        Args:
            recipes: 菜谱列表
            page: 页码（从1开始）
            page_size: 每页大小

        Returns:
            分页结果
        """
        total_records = len(recipes)
        total_pages = math.ceil(total_records / page_size) if total_records > 0 else 0

        # 校验页码
        if page < 1:
            page = 1
        if page > total_pages and total_pages > 0:
            page = total_pages

        # 计算起始和结束索引
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size

        # 获取分页数据
        paginated_data = recipes[start_idx:end_idx]

        return PaginatedResult(
            data=[recipe.to_name_only_dict() for recipe in paginated_data],
            page=page,
            page_size=page_size,
            total_records=total_records,
            total_pages=total_pages,
        )

    def search_recipes(
        self, recipes: List[Recipe], query: str, page: int = 1, page_size: int = 10
    ) -> PaginatedResult:
        """搜索菜谱并分页返回结果.

        Args:
            recipes: 菜谱列表
            query: 搜索关键词
            page: 页码（从1开始）
            page_size: 每页大小

        Returns:
            分页结果
        """
        query_lower = query.lower()
        filtered_recipes = []

        for recipe in recipes:
            # 检查名称
            if query_lower in recipe.name.lower():
                filtered_recipes.append(recipe)
                continue

            # 检查描述
            if query_lower in recipe.description.lower():
                filtered_recipes.append(recipe)
                continue

            # 检查食材
            for ingredient in recipe.ingredients:
                if query_lower in ingredient.name.lower():
                    filtered_recipes.append(recipe)
                    break

        logger.info(f"搜索关键词 '{query}' 找到 {len(filtered_recipes)} 个匹配的菜谱")

        return self.paginate_simple_recipes(filtered_recipes, page, page_size)

    def get_recipes_by_category(
        self, recipes: List[Recipe], category: str, page: int = 1, page_size: int = 10
    ) -> PaginatedResult:
        """根据分类获取菜谱并分页返回结果.

        Args:
            recipes: 菜谱列表
            category: 分类名称
            page: 页码（从1开始）
            page_size: 每页大小

        Returns:
            分页结果
        """
        filtered_recipes = [recipe for recipe in recipes if recipe.category == category]

        logger.info(f"分类 '{category}' 找到 {len(filtered_recipes)} 个菜谱")

        return self.paginate_simple_recipes(filtered_recipes, page, page_size)
