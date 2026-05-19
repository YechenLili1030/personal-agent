"""Reranker — 使用百炼 qwen3-rerank 模型对检索结果重新排序"""

from __future__ import annotations
import logging
import time

from openai import OpenAI

from .base import SearchResult
from ..core.config import BAILIAN_API_KEY, BAILIAN_BASE_URL, RERANK_MODEL

logger = logging.getLogger(__name__)

RERANK_ENDPOINT = f"{BAILIAN_BASE_URL.rstrip('/')}/rerank"


class BailianReranker:
    """调用百炼 qwen3-rerank API 对文档重新打分"""

    def __init__(self, model: str = RERANK_MODEL):
        self.model = model
        self._client = OpenAI(api_key=BAILIAN_API_KEY, base_url=BAILIAN_BASE_URL)

    @property
    def name(self) -> str:
        return f"BailianReranker(model={self.model})"

    async def rerank(self, query: str, results: list[SearchResult],
                     top_k: int = 5) -> list[SearchResult]:
        """对 results 重新排序，返回 top_k"""
        if not results:
            return []

        documents = [r.content for r in results]
        if len(documents) <= top_k:
            return results

        t0 = time.time()
        try:
            resp = self._client.post(
                "/rerank",
                json={
                    "model": self.model,
                    "query": query,
                    "documents": documents,
                    "top_n": top_k,
                },
            )
            data = resp.json()
        except Exception as e:
            logger.warning("Rerank API 调用失败: %s, 回退原始排序", e)
            return results[:top_k]

        elapsed = (time.time() - t0) * 1000
        reranked = data.get("results", [])
        if not reranked:
            logger.warning("Rerank 返回空结果, 回退原始排序")
            return results[:top_k]

        # rerank results: [{index: N, relevance_score: S}, ...]
        out = []
        for item in reranked:
            idx = item["index"]
            r = results[idx]
            r.score = item.get("relevance_score", r.score)
            out.append(r)

        logger.info("Rerank: %d → %d 条 | %.0fms", len(results), len(out), elapsed)
        return out
