"""Configurable RAG retrieval pipeline.

Flow:
    query -> optional rewrite -> parallel retrievers -> fusion -> optional rerank
"""

from __future__ import annotations

import asyncio
import logging
import time

from .base import SearchResult
from ..core.config import DENSE_RECALL_K, RAG_TOP_K, RERANK_TOP_K, SPARSE_RECALL_K

logger = logging.getLogger(__name__)


class RetrievalPipeline:
    def __init__(
        self,
        *,
        rewriter=None,
        retrievers: list | None = None,
        fusion=None,
        reranker=None,
        dense_recall_k: int = DENSE_RECALL_K,
        sparse_recall_k: int = SPARSE_RECALL_K,
        fusion_top_k: int = RAG_TOP_K,
        rerank_top_k: int = RERANK_TOP_K,
    ):
        self.rewriter = rewriter
        self.retrievers = retrievers or []
        self.fusion = fusion
        self.reranker = reranker
        self.dense_recall_k = dense_recall_k
        self.sparse_recall_k = sparse_recall_k
        self.fusion_top_k = fusion_top_k
        self.rerank_top_k = rerank_top_k

    async def run(
        self,
        *,
        query: str,
        history: list[dict] | None = None,
        user_id: str = "",
    ) -> list[SearchResult]:
        started_at = time.time()
        search_query = query

        if self.rewriter:
            search_query = await self.rewriter.rewrite(query, history)

        if not self.retrievers:
            return []

        recall_lists = await self._retrieve_parallel(search_query, user_id)
        if not recall_lists:
            return []

        results = self._merge_results(recall_lists)
        results = await self._rerank_if_needed(query, results)

        elapsed = (time.time() - started_at) * 1000
        logger.info("RAG pipeline done | results=%d | %.0fms", len(results), elapsed)
        return results

    async def _retrieve_parallel(
        self,
        query: str,
        user_id: str,
    ) -> list[list[SearchResult]]:
        tasks = [
            self._retrieve_one(retriever, query, user_id)
            for retriever in self.retrievers
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        recall_lists: list[list[SearchResult]] = []
        for retriever, result in zip(self.retrievers, results):
            if isinstance(result, Exception):
                logger.warning("%s failed: %s", retriever.name, result)
                continue
            if result:
                recall_lists.append(result)

        return recall_lists

    async def _retrieve_one(
        self,
        retriever,
        query: str,
        user_id: str,
    ) -> list[SearchResult]:
        top_k = self._top_k_for(retriever)
        started_at = time.time()
        results = await retriever.retrieve(query, top_k=top_k, user_id=user_id)
        elapsed = (time.time() - started_at) * 1000
        logger.info("%s done | results=%d | %.0fms", retriever.name, len(results), elapsed)
        return results

    def _top_k_for(self, retriever) -> int:
        if retriever.name == "DenseRetriever":
            return self.dense_recall_k
        return self.sparse_recall_k

    def _merge_results(self, recall_lists: list[list[SearchResult]]) -> list[SearchResult]:
        if self.fusion and len(recall_lists) > 1:
            return self.fusion.merge(recall_lists, top_k=self.fusion_top_k)

        if len(recall_lists) == 1:
            return recall_lists[0][:self.fusion_top_k]

        return self._dedupe_without_fusion(recall_lists)

    def _dedupe_without_fusion(
        self,
        recall_lists: list[list[SearchResult]],
    ) -> list[SearchResult]:
        seen = set()
        results = []
        for recall_list in recall_lists:
            for result in recall_list:
                if result.chunk_id in seen:
                    continue
                seen.add(result.chunk_id)
                results.append(result)
        return results[:self.fusion_top_k]

    async def _rerank_if_needed(
        self,
        query: str,
        results: list[SearchResult],
    ) -> list[SearchResult]:
        if not self.reranker or len(results) <= self.rerank_top_k:
            return results

        try:
            return await self.reranker.rerank(query, results, top_k=self.rerank_top_k)
        except Exception as exc:
            logger.warning("Rerank failed: %s", exc)
            return results


_default_pipeline: RetrievalPipeline | None = None


def _build_pipeline_from_config() -> RetrievalPipeline:
    from ..core.config import (
        RAG_DENSE_ENABLED,
        RAG_FUSION_ENABLED,
        RAG_RERANKER_ENABLED,
        RAG_REWRITER_ENABLED,
        RAG_SPARSE_ENABLED,
    )

    rewriter = None
    retrievers = []
    fusion = None
    reranker = None

    if RAG_REWRITER_ENABLED:
        from .query_rewriter import DeepSeekQueryRewriter

        rewriter = DeepSeekQueryRewriter()

    if RAG_DENSE_ENABLED:
        from .dense_retriever import DenseRetriever

        retrievers.append(DenseRetriever())

    if RAG_SPARSE_ENABLED:
        from .sparse_retriever import SparseRetriever

        retrievers.append(SparseRetriever())

    if RAG_FUSION_ENABLED and len(retrievers) > 1:
        from .rrf_fusion import RRFFusion

        fusion = RRFFusion(k=60)

    if RAG_RERANKER_ENABLED:
        from .reranker import BailianReranker

        reranker = BailianReranker()

    pipeline = RetrievalPipeline(
        rewriter=rewriter,
        retrievers=retrievers,
        fusion=fusion,
        reranker=reranker,
    )

    logger.info(
        "RAG pipeline config | rewriter=%s | dense=%s | sparse=%s | fusion=%s | reranker=%s",
        "ON" if rewriter else "OFF",
        "ON" if RAG_DENSE_ENABLED else "OFF",
        "ON" if RAG_SPARSE_ENABLED else "OFF",
        "ON" if fusion else "OFF",
        "ON" if reranker else "OFF",
    )
    return pipeline


def get_pipeline() -> RetrievalPipeline:
    global _default_pipeline
    if _default_pipeline is None:
        _default_pipeline = _build_pipeline_from_config()
    return _default_pipeline


def set_pipeline(pipeline: RetrievalPipeline | None):
    global _default_pipeline
    _default_pipeline = pipeline
