"""
菜谱管理器 - 负责菜谱功能的管理和协调.
"""

import random

from src.utils.logging_config import get_logger

from .client import RecipeClient
from .models import PaginatedResult, RecipeSession

logger = get_logger(__name__)


class RecipeManager:
    """
    菜谱管理器 - 管理菜谱数据缓存和工具功能.
    """

    def __init__(self):
        self.current_session = RecipeSession()
        self.client = RecipeClient()
        self._client_initialized = False
        self._recipes_loaded = False

    async def _ensure_client_initialized(self):
        """
        确保客户端已初始化.
        """
        if not self._client_initialized:
            await self.client.__aenter__()
            self._client_initialized = True

    async def _ensure_recipes_loaded(self):
        """
        确保菜谱数据已加载.
        """
        if not self._recipes_loaded:
            await self.load_recipes()

    async def cleanup(self):
        """
        清理资源.
        """
        if self._client_initialized:
            await self.client.__aexit__(None, None, None)
            self._client_initialized = False

    async def load_recipes(self) -> bool:
        """加载菜谱数据.

        Returns:
            加载是否成功
        """
        try:
            await self._ensure_client_initialized()

            # 获取菜谱数据
            recipes = await self.client.fetch_recipes()

            if not recipes:
                logger.warning("未获取到任何菜谱数据")
                return False

            # 缓存菜谱数据
            self.current_session.add_recipes(recipes)

            # 设置分类
            categories = self.client.get_all_categories(recipes)
            self.current_session.set_categories(categories)

            self._recipes_loaded = True
            logger.info(f"成功加载 {len(recipes)} 个菜谱，{len(categories)} 个分类")
            return True

        except Exception as e:
            logger.error(f"加载菜谱数据失败: {e}")
            return False

    def init_tools(self, add_tool, PropertyList, Property, PropertyType):
        """
        初始化并注册所有菜谱工具.
        """
        from .tools import (
            get_all_recipes,
            get_recipe_by_id,
            get_recipes_by_category,
            recommend_meals,
            search_recipes_fuzzy,
            what_to_eat,
        )

        # 1. 获取所有菜谱工具（分页）
        get_all_recipes_props = PropertyList(
            [
                Property("page", PropertyType.INTEGER, default_value=1),
                Property("page_size", PropertyType.INTEGER, default_value=10),
            ]
        )
        add_tool(
            (
                "self.recipe.get_all_recipes",
                "Get all recipes with pagination support. Returns simplified recipe data "
                "containing only name and description for easy browsing.\n"
                "Use this tool when user wants to:\n"
                "1. Browse all available recipes\n"
                "2. Get an overview of recipe collection\n"
                "3. Find recipes for meal planning\n"
                "4. Explore recipe database without specific search criteria\n"
                "\nFeatures:\n"
                "- Pagination support to avoid overwhelming data\n"
                "- Returns pagination info: current page, page size, total records, total pages\n"
                "- Simplified data format with name and description only\n"
                "- Optimized for recipe list display and browsing\n"
                "- Chinese recipe database with diverse cuisines\n"
                "\nArgs:\n"
                "  page: Page number starting from 1 (default: 1)\n"
                "  page_size: Number of recipes per page (default: 10, max: 20)",
                get_all_recipes_props,
                get_all_recipes,
            )
        )

        # 2. 根据ID获取菜谱详情工具
        get_recipe_by_id_props = PropertyList(
            [
                Property("query", PropertyType.STRING),
            ]
        )
        add_tool(
            (
                "self.recipe.get_recipe_by_id",
                "Get detailed recipe information by ID or name with intelligent matching. "
                "Returns complete recipe details including ingredients, cooking steps, and timing.\n"
                "Use this tool when user wants to:\n"
                "1. Get complete cooking instructions for a specific recipe\n"
                "2. View detailed ingredients and measurements\n"
                "3. Access step-by-step cooking guide\n"
                "4. Check recipe difficulty, cooking time, and servings\n"
                "5. Get comprehensive recipe information for cooking\n"
                "\nMatching Strategy:\n"
                "- Exact match by recipe ID (highest priority)\n"
                "- Exact match by recipe name\n"
                "- Fuzzy match by recipe name (partial matching)\n"
                "- Returns similar recipes if exact match not found\n"
                "- Intelligent suggestions for misspelled queries\n"
                "\nReturned Information:\n"
                "- Complete ingredient list with quantities\n"
                "- Detailed cooking steps with descriptions\n"
                "- Prep time, cook time, and total time\n"
                "- Difficulty level and serving size\n"
                "- Recipe category and tags\n"
                "\nArgs:\n"
                "  query: Recipe name or ID, supports fuzzy matching",
                get_recipe_by_id_props,
                get_recipe_by_id,
            )
        )

        # 3. 根据分类获取菜谱工具（分页）
        get_recipes_by_category_props = PropertyList(
            [
                Property("category", PropertyType.STRING),
                Property("page", PropertyType.INTEGER, default_value=1),
                Property("page_size", PropertyType.INTEGER, default_value=10),
            ]
        )
        add_tool(
            (
                "self.recipe.get_recipes_by_category",
                "Get recipes filtered by category with pagination support. Returns recipes "
                "from specific cuisine categories for targeted meal planning.\n"
                "Use this tool when user wants to:\n"
                "1. Find recipes from a specific cuisine category\n"
                "2. Browse recipes by meal type (breakfast, lunch, dinner)\n"
                "3. Filter recipes by cooking style or ingredient type\n"
                "4. Plan meals with specific dietary preferences\n"
                "5. Explore recipes from particular food categories\n"
                "\nAvailable Categories:\n"
                "- 水产 (Seafood dishes)\n"
                "- 早餐 (Breakfast recipes)\n"
                "- 荤菜 (Meat dishes)\n"
                "- 主食 (Main dishes/staples)\n"
                "- 素菜 (Vegetarian dishes)\n"
                "- 汤羹 (Soups and broths)\n"
                "- 甜品 (Desserts)\n"
                "- 饮品 (Beverages)\n"
                "- And many more categories\n"
                "\nFeatures:\n"
                "- Category-based filtering for precise results\n"
                "- Pagination support for large category collections\n"
                "- Returns simplified recipe data with essential info\n"
                "- Includes pagination metadata\n"
                "\nArgs:\n"
                "  category: Recipe category name (required)\n"
                "  page: Page number starting from 1 (default: 1)\n"
                "  page_size: Number of recipes per page (default: 10, max: 20)",
                get_recipes_by_category_props,
                get_recipes_by_category,
            )
        )

        # 4. 智能推荐菜品工具
        recommend_meals_props = PropertyList(
            [
                Property("people_count", PropertyType.INTEGER, default_value=2),
                Property("meal_type", PropertyType.STRING, default_value="dinner"),
                Property("page", PropertyType.INTEGER, default_value=1),
                Property("page_size", PropertyType.INTEGER, default_value=10),
            ]
        )
        add_tool(
            (
                "self.recipe.recommend_meals",
                "Get intelligent meal recommendations based on number of people and meal type. "
                "Provides balanced recipe suggestions suitable for different dining scenarios.\n"
                "Use this tool when user wants to:\n"
                "1. Get meal suggestions for a specific number of people\n"
                "2. Plan appropriate dishes for different meal times\n"
                "3. Find balanced meal combinations (meat and vegetables)\n"
                "4. Get quick meal planning recommendations\n"
                "5. Discover suitable recipes for group dining\n"
                "\nRecommendation Logic:\n"
                "- Adjusts recipe suggestions based on people count\n"
                "- Filters recipes by meal type preferences\n"
                "- Balances meat dishes and vegetarian options\n"
                "- Considers appropriate portion sizes and complexity\n"
                "- Provides diverse cuisine options\n"
                "\nMeal Types:\n"
                "- breakfast: Morning meal recipes\n"
                "- lunch: Midday meal suggestions\n"
                "- dinner: Evening dining options\n"
                "- any: All meal types included\n"
                "\nArgs:\n"
                "  people_count: Number of people dining (default: 2)\n"
                "  meal_type: Type of meal - breakfast/lunch/dinner (default: dinner)\n"
                "  page: Page number starting from 1 (default: 1)\n"
                "  page_size: Number of recipes per page (default: 10, max: 20)",
                recommend_meals_props,
                recommend_meals,
            )
        )

        # 5. 随机推荐菜品工具
        what_to_eat_props = PropertyList(
            [
                Property("meal_type", PropertyType.STRING, default_value="any"),
                Property("page", PropertyType.INTEGER, default_value=1),
                Property("page_size", PropertyType.INTEGER, default_value=10),
            ]
        )
        add_tool(
            (
                "self.recipe.what_to_eat",
                "Get random recipe suggestions to solve the 'what should I eat?' dilemma. "
                "Provides serendipitous recipe discoveries with optional meal type filtering.\n"
                "Use this tool when user wants to:\n"
                "1. Get inspiration when unsure what to cook\n"
                "2. Discover new recipes randomly\n"
                "3. Find surprise meal options\n"
                "4. Break routine with unexpected recipe suggestions\n"
                "5. Explore diverse cuisine options without specific criteria\n"
                "\nRandomization Features:\n"
                "- True random recipe selection for surprise factor\n"
                "- Optional meal type filtering for relevance\n"
                "- Diverse cuisine representation\n"
                "- Balanced difficulty levels\n"
                "- Fresh suggestions on each call\n"
                "\nMeal Type Options:\n"
                "- breakfast: Random morning meal ideas\n"
                "- lunch: Random midday dining options\n"
                "- dinner: Random evening meal suggestions\n"
                "- any: Completely random from all categories\n"
                "\nPerfect for:\n"
                "- Decision paralysis situations\n"
                "- Culinary adventure seeking\n"
                "- Breaking cooking routines\n"
                "- Quick meal inspiration\n"
                "\nArgs:\n"
                "  meal_type: Meal type filter - breakfast/lunch/dinner/any (default: any)\n"
                "  page: Page number starting from 1 (default: 1)\n"
                "  page_size: Number of recipes per page (default: 10, max: 20)",
                what_to_eat_props,
                what_to_eat,
            )
        )

        # 6. 模糊搜索菜谱工具（新增功能）
        search_recipes_fuzzy_props = PropertyList(
            [
                Property("query", PropertyType.STRING),
                Property("page", PropertyType.INTEGER, default_value=1),
                Property("page_size", PropertyType.INTEGER, default_value=10),
            ]
        )
        add_tool(
            (
                "self.recipe.search_recipes",
                "Search recipes using fuzzy keyword matching across recipe names, descriptions, "
                "and ingredients. Perfect for finding recipes containing specific ingredients or keywords.\n"
                "Use this tool when user wants to:\n"
                "1. Find recipes containing specific ingredients (e.g., '花甲', '鸡蛋')\n"
                "2. Search for recipes by cooking method or style\n"
                "3. Discover recipes with particular flavors or characteristics\n"
                "4. Find alternatives when exact recipe name is unknown\n"
                "5. Explore recipes related to dietary requirements\n"
                "\nSearch Capabilities:\n"
                "- Fuzzy matching in recipe names for flexible search\n"
                "- Description matching for cooking style and flavor discovery\n"
                "- Ingredient matching for finding recipes with specific components\n"
                "- Case-insensitive search for user convenience\n"
                "- Partial keyword matching for broader results\n"
                "\nSearch Examples:\n"
                "- '花甲' → finds all recipes containing clams\n"
                "- '鸡蛋' → finds all egg-based recipes\n"
                "- '辣' → finds spicy dishes\n"
                "- '素食' → finds vegetarian options\n"
                "- '汤' → finds soup recipes\n"
                "\nFeatures:\n"
                "- Intelligent keyword matching algorithm\n"
                "- Pagination support for large result sets\n"
                "- Returns simplified recipe data for easy browsing\n"
                "- Includes search metadata and result counts\n"
                "\nArgs:\n"
                "  query: Search keyword or ingredient name (required)\n"
                "  page: Page number starting from 1 (default: 1)\n"
                "  page_size: Number of recipes per page (default: 10, max: 20)",
                search_recipes_fuzzy_props,
                search_recipes_fuzzy,
            )
        )

    async def get_all_recipes(
        self, page: int = 1, page_size: int = 10
    ) -> PaginatedResult:
        """获取所有菜谱（分页）.

        Args:
            page: 页码
            page_size: 每页大小

        Returns:
            分页结果
        """
        await self._ensure_recipes_loaded()

        recipes = list(self.current_session.recipes.values())
        return self.client.paginate_name_only_recipes(recipes, page, page_size)

    async def get_recipe_by_id(self, query: str) -> dict:
        """根据ID或名称获取菜谱详情.

        Args:
            query: 菜谱ID或名称

        Returns:
            菜谱详情或错误信息
        """
        await self._ensure_recipes_loaded()

        # 首先尝试精确匹配ID
        recipe = self.current_session.get_recipe(query)
        if recipe:
            return recipe.to_dict()

        # 尝试精确匹配名称
        for recipe in self.current_session.recipes.values():
            if recipe.name == query:
                return recipe.to_dict()

        # 尝试模糊匹配名称
        for recipe in self.current_session.recipes.values():
            if query.lower() in recipe.name.lower():
                return recipe.to_dict()

        # 如果还没找到，返回所有可能的匹配项（最多5个）
        possible_matches = []
        for recipe in self.current_session.recipes.values():
            if (
                query.lower() in recipe.name.lower()
                or query.lower() in recipe.description.lower()
            ):
                possible_matches.append(
                    {
                        "id": recipe.id,
                        "name": recipe.name,
                        "description": recipe.description,
                        "category": recipe.category,
                    }
                )
                if len(possible_matches) >= 5:
                    break

        if not possible_matches:
            return {
                "error": "未找到匹配的菜谱",
                "query": query,
                "suggestion": "请检查菜谱名称是否正确，或尝试使用关键词搜索",
            }

        return {
            "message": "未找到精确匹配，以下是可能的匹配项：",
            "query": query,
            "possible_matches": possible_matches,
        }

    async def get_recipes_by_category(
        self, category: str, page: int = 1, page_size: int = 10
    ) -> PaginatedResult:
        """根据分类获取菜谱（分页）.

        Args:
            category: 分类名称
            page: 页码
            page_size: 每页大小

        Returns:
            分页结果
        """
        await self._ensure_recipes_loaded()

        recipes = list(self.current_session.recipes.values())
        return self.client.get_recipes_by_category(recipes, category, page, page_size)

    async def search_recipes(
        self, query: str, page: int = 1, page_size: int = 10
    ) -> PaginatedResult:
        """搜索菜谱（分页）.

        Args:
            query: 搜索关键词
            page: 页码
            page_size: 每页大小

        Returns:
            分页结果
        """
        await self._ensure_recipes_loaded()

        recipes = list(self.current_session.recipes.values())
        return self.client.search_recipes(recipes, query, page, page_size)

    async def recommend_meals(
        self,
        people_count: int = 2,
        meal_type: str = "dinner",
        page: int = 1,
        page_size: int = 10,
    ) -> PaginatedResult:
        """推荐菜品（分页）.

        Args:
            people_count: 用餐人数
            meal_type: 用餐类型
            page: 页码
            page_size: 每页大小

        Returns:
            分页结果
        """
        await self._ensure_recipes_loaded()

        # 根据用餐类型筛选菜谱
        all_recipes = list(self.current_session.recipes.values())

        if meal_type == "breakfast":
            filtered_recipes = [
                r for r in all_recipes if "早餐" in r.category or "早餐" in r.name
            ]
        elif meal_type == "lunch":
            filtered_recipes = [
                r for r in all_recipes if "午餐" in r.category or "主食" in r.category
            ]
        elif meal_type == "dinner":
            filtered_recipes = [
                r
                for r in all_recipes
                if "晚餐" in r.category or "荤菜" in r.category or "素菜" in r.category
            ]
        else:
            filtered_recipes = all_recipes

        # 如果没有找到合适的菜谱，使用所有菜谱
        if not filtered_recipes:
            filtered_recipes = all_recipes

        # 随机排序
        random.shuffle(filtered_recipes)

        return self.client.paginate_simple_recipes(filtered_recipes, page, page_size)

    async def what_to_eat(
        self, meal_type: str = "any", page: int = 1, page_size: int = 10
    ) -> PaginatedResult:
        """随机推荐菜品（分页）.

        Args:
            meal_type: 用餐类型
            page: 页码
            page_size: 每页大小

        Returns:
            分页结果
        """
        await self._ensure_recipes_loaded()

        # 根据用餐类型筛选菜谱
        all_recipes = list(self.current_session.recipes.values())

        if meal_type == "breakfast":
            filtered_recipes = [
                r for r in all_recipes if "早餐" in r.category or "早餐" in r.name
            ]
        elif meal_type == "lunch":
            filtered_recipes = [
                r for r in all_recipes if "午餐" in r.category or "主食" in r.category
            ]
        elif meal_type == "dinner":
            filtered_recipes = [
                r
                for r in all_recipes
                if "晚餐" in r.category or "荤菜" in r.category or "素菜" in r.category
            ]
        else:
            filtered_recipes = all_recipes

        # 如果没有找到合适的菜谱，使用所有菜谱
        if not filtered_recipes:
            filtered_recipes = all_recipes

        # 随机排序
        random.shuffle(filtered_recipes)

        return self.client.paginate_simple_recipes(filtered_recipes, page, page_size)

    def get_session_info(self) -> dict:
        """
        获取当前会话信息.
        """
        return {
            "session_id": self.current_session.id,
            "total_recipes": len(self.current_session.recipes),
            "total_categories": len(self.current_session.categories),
            "categories": self.current_session.categories,
            "recipes_loaded": self._recipes_loaded,
            "created_at": self.current_session.created_at,
            "last_accessed": self.current_session.last_accessed,
        }


# 全局管理器实例
_recipe_manager = None


def get_recipe_manager() -> RecipeManager:
    """
    获取菜谱管理器单例.
    """
    global _recipe_manager
    if _recipe_manager is None:
        _recipe_manager = RecipeManager()
    return _recipe_manager


async def cleanup_recipe_manager():
    """
    清理菜谱管理器资源.
    """
    global _recipe_manager
    if _recipe_manager:
        await _recipe_manager.cleanup()
        _recipe_manager = None
