"""稀疏检索 — BM25 关键词匹配适配器"""

from __future__ import annotations
import logging

from .base import SearchResult
from ..services.bm25_store import get_bm25_store

logger = logging.getLogger(__name__)


class SparseRetriever:
    """基于 BM25 的稀疏关键词检索"""

    @property
    def name(self) -> str:
        return "SparseRetriever"

    async def retrieve(self, query: str, top_k: int = 20,
                       user_id: str = "", **kwargs) -> list[SearchResult]:
        bm25 = get_bm25_store()
        results = bm25.search(query, top_k=top_k, user_id=user_id or None)
        logger.info("稀疏检索: query='%s' -> %d 条", query[:60], len(results))
        return [SearchResult.from_dict(r) for r in results]
