"""
搜索数据模型.
"""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional


class SearchResult:
    """
    搜索结果数据模型.
    """

    def __init__(
        self,
        title: str,
        url: str,
        snippet: str,
        result_id: str = None,
        content: str = None,
        source: str = "bing",
        created_at: str = None,
    ):
        self.id = result_id or str(uuid.uuid4())
        self.title = title
        self.url = url
        self.snippet = snippet
        self.content = content
        self.source = source
        self.created_at = created_at or datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典.
        """
        return {
            "id": self.id,
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet,
            "content": self.content,
            "source": self.source,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SearchResult":
        """
        从字典创建搜索结果.
        """
        return cls(
            title=data.get("title", ""),
            url=data.get("url", ""),
            snippet=data.get("snippet", ""),
            result_id=data.get("id"),
            content=data.get("content"),
            source=data.get("source", "bing"),
            created_at=data.get("created_at"),
        )


class SearchQuery:
    """
    搜索查询模型.
    """

    def __init__(
        self,
        query: str,
        num_results: int = 5,
        language: str = "zh-cn",
        region: str = "CN",
        safe_search: str = "moderate",
        query_id: str = None,
    ):
        self.id = query_id or str(uuid.uuid4())
        self.query = query
        self.num_results = num_results
        self.language = language
        self.region = region
        self.safe_search = safe_search
        self.created_at = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典.
        """
        return {
            "id": self.id,
            "query": self.query,
            "num_results": self.num_results,
            "language": self.language,
            "region": self.region,
            "safe_search": self.safe_search,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SearchQuery":
        """
        从字典创建搜索查询.
        """
        return cls(
            query=data.get("query", ""),
            num_results=data.get("num_results", 5),
            language=data.get("language", "zh-cn"),
            region=data.get("region", "CN"),
            safe_search=data.get("safe_search", "moderate"),
            query_id=data.get("id"),
        )


class SearchSession:
    """
    搜索会话模型，用于缓存搜索结果.
    """

    def __init__(self, session_id: str = None):
        self.id = session_id or str(uuid.uuid4())
        self.results: Dict[str, SearchResult] = {}
        self.queries: List[SearchQuery] = []
        self.created_at = datetime.now().isoformat()
        self.last_accessed = datetime.now().isoformat()

    def add_result(self, result: SearchResult) -> None:
        """
        添加搜索结果到会话.
        """
        self.results[result.id] = result
        self.last_accessed = datetime.now().isoformat()

    def get_result(self, result_id: str) -> Optional[SearchResult]:
        """
        从会话中获取搜索结果.
        """
        self.last_accessed = datetime.now().isoformat()
        return self.results.get(result_id)

    def add_query(self, query: SearchQuery) -> None:
        """
        添加搜索查询到会话.
        """
        self.queries.append(query)
        self.last_accessed = datetime.now().isoformat()

    def clear_results(self) -> None:
        """
        清空搜索结果.
        """
        self.results.clear()
        self.last_accessed = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典.
        """
        return {
            "id": self.id,
            "results": {k: v.to_dict() for k, v in self.results.items()},
            "queries": [q.to_dict() for q in self.queries],
            "created_at": self.created_at,
            "last_accessed": self.last_accessed,
        }
