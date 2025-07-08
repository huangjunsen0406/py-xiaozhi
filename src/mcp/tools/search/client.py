"""
搜索客户端 - 实现异步的必应搜索和网页内容获取功能.
"""

import re
from typing import List, Optional
from urllib.parse import urlencode

import aiohttp
from bs4 import BeautifulSoup

from src.utils.logging_config import get_logger

from .models import SearchQuery, SearchResult

logger = get_logger(__name__)


class SearchClient:
    """
    异步搜索客户端.
    """

    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.user_agent = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        self.base_headers = {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1",
            "Cookie": "SRCHHPGUSR=SRCHLANG=zh-Hans; _EDGE_S=ui=zh-cn; _EDGE_V=1",
        }
        self.timeout = aiohttp.ClientTimeout(total=15)

    async def __aenter__(self):
        """
        异步上下文管理器入口.
        """
        if self.session is None:
            self.session = aiohttp.ClientSession(
                timeout=self.timeout,
                headers=self.base_headers,
                connector=aiohttp.TCPConnector(limit=10, limit_per_host=5),
            )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """
        异步上下文管理器出口.
        """
        if self.session:
            await self.session.close()

    async def search_bing(self, query: SearchQuery) -> List[SearchResult]:
        """执行必应搜索.

        Args:
            query: 搜索查询对象

        Returns:
            搜索结果列表
        """
        try:
            if not self.session:
                raise RuntimeError(
                    "SearchClient not initialized. Use 'async with' statement."
                )

            # 构建搜索URL
            search_params = {
                "q": query.query,
                "setlang": query.language,
                "ensearch": "0",
                "count": str(query.num_results),
            }

            search_url = f"https://cn.bing.com/search?{urlencode(search_params)}"
            logger.info(f"正在搜索: {search_url}")

            # 发送请求
            async with self.session.get(search_url) as response:
                response.raise_for_status()
                html = await response.text()
                logger.info(f"搜索响应状态: {response.status}")

            # 解析搜索结果
            results = await self._parse_search_results(html, query)
            logger.info(f"解析得到 {len(results)} 个搜索结果")

            return results

        except Exception as e:
            logger.error(f"必应搜索失败: {e}")
            # 返回错误信息作为搜索结果
            error_result = SearchResult(
                title=f'搜索 "{query.query}" 时出错',
                url=f"https://cn.bing.com/search?q={query.query}",
                snippet=f"搜索过程中发生错误: {str(e)}",
                source="bing",
            )
            return [error_result]

    async def _parse_search_results(
        self, html: str, query: SearchQuery
    ) -> List[SearchResult]:
        """解析搜索结果页面.

        Args:
            html: 搜索结果页面HTML
            query: 搜索查询对象

        Returns:
            搜索结果列表
        """
        soup = BeautifulSoup(html, "html.parser")
        results = []

        # 尝试多种选择器策略
        selectors = [
            "#b_results > li.b_algo",
            "#b_results > .b_ans",
            "#b_results > li:not(.b_ad)",
            ".b_algo",
        ]

        for selector in selectors:
            elements = soup.select(selector)
            logger.info(f"选择器 '{selector}' 找到 {len(elements)} 个元素")

            for i, element in enumerate(elements):
                if len(results) >= query.num_results:
                    break

                try:
                    # 提取标题和链接
                    title_element = element.select_one("h2 a")
                    if not title_element:
                        title_element = element.select_one(".b_title a")

                    if title_element:
                        title = title_element.get_text(strip=True)
                        url = title_element.get("href", "")

                        # 修复相对链接
                        if url.startswith("/"):
                            url = f"https://cn.bing.com{url}"

                        # 提取摘要
                        snippet_element = element.select_one(".b_caption p")
                        if not snippet_element:
                            snippet_element = element.select_one(".b_snippet")

                        snippet = ""
                        if snippet_element:
                            snippet = snippet_element.get_text(strip=True)

                        # 如果没有摘要，尝试获取元素的文本内容
                        if not snippet:
                            text = element.get_text(strip=True)
                            if title in text:
                                text = text.replace(title, "", 1)
                            snippet = text[:200] + "..." if len(text) > 200 else text

                        # 跳过无效结果
                        if not title or not url:
                            continue

                        result = SearchResult(
                            title=title,
                            url=url,
                            snippet=snippet,
                            source="bing",
                        )
                        results.append(result)

                except Exception as e:
                    logger.warning(f"解析搜索结果元素失败: {e}")
                    continue

            # 如果找到了结果，停止尝试其他选择器
            if results:
                break

        # 如果没有找到任何结果，返回一个默认结果
        if not results:
            logger.warning("未找到任何搜索结果，返回默认结果")
            default_result = SearchResult(
                title=f"搜索结果: {query.query}",
                url=f"https://cn.bing.com/search?q={query.query}",
                snippet=f'未能解析关于 "{query.query}" 的搜索结果，但您可以直接访问必应搜索页面查看。',
                source="bing",
            )
            results.append(default_result)

        return results

    async def fetch_webpage_content(self, url: str, max_length: int = 8000) -> str:
        """获取网页内容.

        Args:
            url: 网页URL
            max_length: 最大内容长度

        Returns:
            网页文本内容
        """
        try:
            if not self.session:
                raise RuntimeError(
                    "SearchClient not initialized. Use 'async with' statement."
                )

            logger.info(f"正在获取网页内容: {url}")

            # 设置请求头
            headers = self.base_headers.copy()
            headers["Referer"] = "https://cn.bing.com/"

            async with self.session.get(url, headers=headers) as response:
                # 检查响应状态
                response.raise_for_status()

                # 获取内容类型
                content_type = response.headers.get("content-type", "").lower()
                if "text/html" not in content_type:
                    return f"不支持的内容类型: {content_type}"

                # 读取内容
                content = await response.read()

                # 尝试检测编码
                encoding = "utf-8"
                charset_match = re.search(r"charset=([^;]+)", content_type)
                if charset_match:
                    encoding = charset_match.group(1).strip()

                try:
                    html = content.decode(encoding)
                except UnicodeDecodeError:
                    logger.warning(f"使用 {encoding} 解码失败，回退到 utf-8")
                    html = content.decode("utf-8", errors="ignore")

                # 解析网页内容
                return await self._extract_webpage_content(html, url, max_length)

        except Exception as e:
            logger.error(f"获取网页内容失败: {e}")
            raise Exception(f"获取网页内容失败: {str(e)}")

    async def _extract_webpage_content(
        self, html: str, url: str, max_length: int
    ) -> str:
        """从HTML中提取主要内容.

        Args:
            html: HTML内容
            url: 网页URL
            max_length: 最大内容长度

        Returns:
            提取的文本内容
        """
        soup = BeautifulSoup(html, "html.parser")

        # 移除不需要的元素
        for tag in soup(
            ["script", "style", "iframe", "noscript", "nav", "header", "footer"]
        ):
            tag.decompose()

        # 移除具有特定类名的元素
        for selector in [
            ".ad",
            ".advertisement",
            ".sidebar",
            ".nav",
            ".header",
            ".footer",
        ]:
            for element in soup.select(selector):
                element.decompose()

        # 尝试找到主要内容区域
        main_content = ""
        content_selectors = [
            "main",
            "article",
            ".article",
            ".post",
            ".content",
            "#content",
            ".main",
            "#main",
            ".body",
            "#body",
            ".entry",
            ".entry-content",
            ".post-content",
            ".article-content",
            ".text",
            ".detail",
        ]

        for selector in content_selectors:
            element = soup.select_one(selector)
            if element:
                main_content = element.get_text(separator=" ", strip=True)
                if len(main_content) > 100:  # 内容足够长
                    break

        # 如果没有找到主要内容，尝试提取所有段落
        if not main_content or len(main_content) < 100:
            paragraphs = []
            for p in soup.find_all("p"):
                text = p.get_text(strip=True)
                if len(text) > 20:  # 只保留有意义的段落
                    paragraphs.append(text)

            if paragraphs:
                main_content = "\n\n".join(paragraphs)

        # 如果仍然没有内容，获取body内容
        if not main_content or len(main_content) < 100:
            body = soup.find("body")
            if body:
                main_content = body.get_text(separator=" ", strip=True)

        # 清理文本
        main_content = re.sub(r"\s+", " ", main_content).strip()

        # 添加标题
        title_element = soup.find("title")
        if title_element:
            title = title_element.get_text(strip=True)
            main_content = f"标题: {title}\n\n{main_content}"

        # 限制内容长度
        if len(main_content) > max_length:
            main_content = main_content[:max_length] + "... (内容已截断)"

        return main_content if main_content else "无法提取网页内容"
