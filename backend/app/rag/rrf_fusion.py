"""RRF 融合 — Reciprocal Rank Fusion 多路结果合并"""

from __future__ import annotations
import logging
from collections import defaultdict

from .base import SearchResult

logger = logging.getLogger(__name__)


class RRFFusion:
    """Reciprocal Rank Fusion"""

    def __init__(self, k: int = 60):
        self.k = k

    @property
    def name(self) -> str:
        return f"RRFFusion(k={self.k})"

    def merge(self, result_lists: list[list[SearchResult]],
              top_k: int = 10) -> list[SearchResult]:
        """合并多路检索结果，按 RRF 分数降序取 top_k"""
        lookup: dict[str, SearchResult] = {}
        scores: dict[str, float] = defaultdict(float)

        for results in result_lists:
            for rank, r in enumerate(results):
                cid = r.chunk_id
                if cid not in lookup:
                    lookup[cid] = r
                scores[cid] += 1.0 / (self.k + rank + 1)

        sorted_ids = sorted(scores, key=lambda x: scores[x], reverse=True)
        merged = [lookup[cid] for cid in sorted_ids[:top_k]]
        logger.info("RRF 融合: %d 路 → %d 条 (取 top_%d)",
                     len(result_lists), len(merged), top_k)
        return merged
