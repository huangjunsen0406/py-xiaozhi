"""
搜索管理器 - 负责搜索功能的管理和协调.
"""

from typing import List

from src.utils.logging_config import get_logger

from .client import SearchClient
from .models import SearchQuery, SearchResult, SearchSession

logger = get_logger(__name__)


class SearchManager:
    """
    搜索管理器 - 管理搜索会话和结果缓存.
    """

    def __init__(self):
        self.current_session = SearchSession()
        self.client = SearchClient()
        self._client_initialized = False

    async def _ensure_client_initialized(self):
        """
        确保搜索客户端已初始化.
        """
        if not self._client_initialized:
            await self.client.__aenter__()
            self._client_initialized = True

    async def cleanup(self):
        """
        清理资源.
        """
        if self._client_initialized:
            await self.client.__aexit__(None, None, None)
            self._client_initialized = False

    def init_tools(self, add_tool, PropertyList, Property, PropertyType):
        """
        初始化并注册所有搜索工具.
        """
        from .tools import fetch_webpage_content, get_search_results, search_bing

        # 必应搜索工具
        search_bing_props = PropertyList(
            [
                Property("query", PropertyType.STRING),
                Property("num_results", PropertyType.INTEGER, default_value=5),
                Property("language", PropertyType.STRING, default_value="zh-cn"),
                Property("region", PropertyType.STRING, default_value="CN"),
            ]
        )
        add_tool(
            (
                "self.search.bing_search",
                "Execute Bing search with Chinese optimization and return structured "
                "search results. Designed specifically for Chinese users with proper "
                "language and region settings.\n"
                "Use this tool when user wants to:\n"
                "1. Search for information on the internet\n"
                "2. Find recent news, articles, or web content\n"
                "3. Look up specific topics, people, or events\n"
                "4. Research current information beyond training data\n"
                "5. Find official websites or documentation\n"
                "\nFeatures:\n"
                "- Optimized for Chinese search results\n"
                "- Intelligent content parsing and extraction\n"
                "- Fallback mechanisms for robust search\n"
                "- Structured result format with title, URL, and snippet\n"
                "- Automatic result caching for follow-up content fetching\n"
                "\nSearch Quality:\n"
                "- Uses cn.bing.com for better Chinese content\n"
                "- Proper language and region targeting\n"
                "- Anti-blocking measures with proper headers\n"
                "- Multiple parsing strategies for reliable results\n"
                "\nArgs:\n"
                "  query: Search keywords or phrase (required)\n"
                "  num_results: Number of results to return (default: 5, max: 10)\n"
                "  language: Search language code (default: 'zh-cn')\n"
                "  region: Search region code (default: 'CN')",
                search_bing_props,
                search_bing,
            )
        )

        # 网页内容获取工具
        fetch_webpage_props = PropertyList(
            [
                Property("result_id", PropertyType.STRING),
                Property("max_length", PropertyType.INTEGER, default_value=8000),
            ]
        )
        add_tool(
            (
                "self.search.fetch_webpage",
                "Fetch and extract the main content from a webpage using the "
                "result ID obtained from bing_search. Intelligently extracts the "
                "main content while filtering out navigation, ads, and irrelevant "
                "elements.\n"
                "Use this tool when user wants to:\n"
                "1. Read the full content of a search result\n"
                "2. Get detailed information from a specific webpage\n"
                "3. Extract main content from articles or blog posts\n"
                "4. Access content that's summarized in search snippets\n"
                "5. Analyze or process webpage content for specific information\n"
                "\nContent Extraction Features:\n"
                "- Intelligent main content detection\n"
                "- Removes ads, navigation, and irrelevant elements\n"
                "- Handles various webpage structures and layouts\n"
                "- Preserves text formatting and structure\n"
                "- Automatic encoding detection and handling\n"
                "\nText Processing:\n"
                "- Extracts meaningful paragraphs and sections\n"
                "- Preserves article titles and headings\n"
                "- Cleans up whitespace and formatting\n"
                "- Configurable content length limits\n"
                "- Fallback strategies for difficult-to-parse pages\n"
                "\nArgs:\n"
                "  result_id: The ID of the search result from bing_search (required)\n"
                "  max_length: Maximum content length in characters (default: 8000)",
                fetch_webpage_props,
                fetch_webpage_content,
            )
        )

        # 获取搜索结果工具
        get_results_props = PropertyList(
            [
                Property("session_id", PropertyType.STRING, default_value=""),
            ]
        )
        add_tool(
            (
                "self.search.get_results",
                "Get all cached search results from the current or specified "
                "search session. Returns a list of all search results that were "
                "obtained from previous search operations.\n"
                "Use this tool when user wants to:\n"
                "1. Review previous search results\n"
                "2. Get a summary of all found results\n"
                "3. Reference search results by ID for content fetching\n"
                "4. Check what information is available from recent searches\n"
                "\nArgs:\n"
                "  session_id: Optional session ID (default: current session)",
                get_results_props,
                get_search_results,
            )
        )

    async def search(
        self,
        query: str,
        num_results: int = 5,
        language: str = "zh-cn",
        region: str = "CN",
    ) -> List[SearchResult]:
        """执行搜索并缓存结果.

        Args:
            query: 搜索关键词
            num_results: 返回结果数量
            language: 搜索语言
            region: 搜索区域

        Returns:
            搜索结果列表
        """
        try:
            await self._ensure_client_initialized()

            # 创建搜索查询
            search_query = SearchQuery(
                query=query,
                num_results=num_results,
                language=language,
                region=region,
            )

            # 执行搜索
            results = await self.client.search_bing(search_query)

            # 缓存结果
            for result in results:
                self.current_session.add_result(result)

            # 记录查询
            self.current_session.add_query(search_query)

            logger.info(f"搜索完成: {query}, 返回 {len(results)} 个结果")
            return results

        except Exception as e:
            logger.error(f"搜索失败: {e}")
            raise e

    async def fetch_content(self, result_id: str, max_length: int = 8000) -> str:
        """获取网页内容.

        Args:
            result_id: 搜索结果ID
            max_length: 最大内容长度

        Returns:
            网页内容
        """
        try:
            await self._ensure_client_initialized()

            # 从缓存中获取搜索结果
            result = self.current_session.get_result(result_id)
            if not result:
                raise ValueError(f"找不到ID为 {result_id} 的搜索结果")

            # 获取网页内容
            content = await self.client.fetch_webpage_content(result.url, max_length)

            # 更新搜索结果的内容
            result.content = content
            self.current_session.add_result(result)  # 更新缓存

            logger.info(f"获取网页内容完成: {result.url}")
            return content

        except Exception as e:
            logger.error(f"获取网页内容失败: {e}")
            raise e

    def get_cached_results(self, session_id: str = None) -> List[SearchResult]:
        """获取缓存的搜索结果.

        Args:
            session_id: 会话ID，如果为None则使用当前会话

        Returns:
            搜索结果列表
        """
        if session_id and session_id != self.current_session.id:
            # 如果指定了不同的会话ID，暂时返回空列表
            # 在实际应用中可以实现多会话管理
            return []

        return list(self.current_session.results.values())

    def clear_cache(self):
        """
        清空搜索缓存.
        """
        self.current_session.clear_results()
        logger.info("搜索缓存已清空")

    def get_session_info(self) -> dict:
        """
        获取当前会话信息.
        """
        return {
            "session_id": self.current_session.id,
            "total_results": len(self.current_session.results),
            "total_queries": len(self.current_session.queries),
            "created_at": self.current_session.created_at,
            "last_accessed": self.current_session.last_accessed,
        }


# 全局管理器实例
_search_manager = None


def get_search_manager() -> SearchManager:
    """
    获取搜索管理器单例.
    """
    global _search_manager
    if _search_manager is None:
        _search_manager = SearchManager()
    return _search_manager


async def cleanup_search_manager():
    """
    清理搜索管理器资源.
    """
    global _search_manager
    if _search_manager:
        await _search_manager.cleanup()
        _search_manager = None
