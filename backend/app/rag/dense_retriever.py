"""稠密检索 — ChromaDB 向量相似度适配器"""

from __future__ import annotations
import logging

from .base import SearchResult
from ..services.embedding import embed_single
from ..services.vector_store import query as vector_query

logger = logging.getLogger(__name__)


class DenseRetriever:
    """基于 ChromaDB 的向量稠密检索"""

    def __init__(self, collection: str = "knowledge_base"):
        self._collection = collection

    @property
    def name(self) -> str:
        return "DenseRetriever"

    async def retrieve(self, query: str, top_k: int = 20,
                       user_id: str = "", **kwargs) -> list[SearchResult]:
        query_emb = await embed_single(query)
        results = vector_query(query_emb, top_k=top_k, user_id=user_id or None)
        logger.info("稠密检索: query='%s' -> %d 条", query[:60], len(results))
        return [SearchResult.from_dict(r) for r in results]
