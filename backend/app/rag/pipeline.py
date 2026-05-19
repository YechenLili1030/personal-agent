"""RAG 检索流水线 — 可插拔组件的编排器

使用示例:
    pipeline = RetrievalPipeline(
        rewriter=DeepSeekQueryRewriter(),
        retrievers=[DenseRetriever(), SparseRetriever()],
        fusion=RRFFusion(k=60),
        reranker=BailianReranker(),
    )
    results = await pipeline.run(query="...", history=[...], user_id="...")
"""

from __future__ import annotations
import logging
import time

from .base import SearchResult
from ..core.config import (
    DENSE_RECALL_K, SPARSE_RECALL_K,
    RAG_TOP_K, RERANK_TOP_K,
)

logger = logging.getLogger(__name__)


class RetrievalPipeline:
    """可配置的 RAG 检索流水线

    ── 流程 ──
    query → [rewriter] → retrievers → fusion → [reranker] → results
    """

    def __init__(self, *,
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

    async def run(self, *, query: str, history: list[dict] | None = None,
                  user_id: str = "") -> list[SearchResult]:
        """执行完整检索流水线，返回最终结果列表"""
        results = []
        t0 = time.time()

        # ━━━ 1. 查询改写 ━━━
        search_query = query
        if self.rewriter:
            search_query = await self.rewriter.rewrite(query, history)

        # ━━━ 2. 多路检索 ━━━
        if not self.retrievers:
            return results

        recall_lists: list[list[SearchResult]] = []
        for retriever in self.retrievers:
            try:
                # 稠密检索用更小 recall，稀疏检索用更大 recall
                top_k = (self.dense_recall_k
                         if retriever.name == "DenseRetriever"
                         else self.sparse_recall_k)
                chunk_list = await retriever.retrieve(
                    search_query, top_k=top_k, user_id=user_id)
                recall_lists.append(chunk_list)
            except Exception as e:
                logger.warning("%s 检索失败: %s", retriever.name, e)

        if not recall_lists:
            return results

        # ━━━ 3. 融合 ━━━
        if self.fusion and len(recall_lists) > 1:
            results = self.fusion.merge(recall_lists, top_k=self.fusion_top_k)
        elif len(recall_lists) == 1:
            results = recall_lists[0][:self.fusion_top_k]
        else:
            # 多路无融合: 简单拼接去重取 top
            seen = set()
            results = []
            for rl in recall_lists:
                for r in rl:
                    if r.chunk_id not in seen:
                        seen.add(r.chunk_id)
                        results.append(r)
            results = results[:self.fusion_top_k]

        # ━━━ 4. 重排序 ━━━
        if self.reranker and len(results) > self.rerank_top_k:
            try:
                results = await self.reranker.rerank(
                    query, results, top_k=self.rerank_top_k)
            except Exception as e:
                logger.warning("Rerank 失败: %s", e)

        elapsed = (time.time() - t0) * 1000
        logger.info("流水线完成: %d 条结果 | %.0fms", len(results), elapsed)
        return results


# ── 默认流水线工厂 ──

_default_pipeline: RetrievalPipeline | None = None


def _build_pipeline_from_config() -> RetrievalPipeline:
    """根据环境变量构建流水线，每个组件可独立开关"""
    from ..core.config import (
        RAG_REWRITER_ENABLED, RAG_DENSE_ENABLED, RAG_SPARSE_ENABLED,
        RAG_FUSION_ENABLED, RAG_RERANKER_ENABLED,
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

    parts = []
    parts.append(f"rewriter={'ON' if rewriter else 'OFF'}")
    parts.append(f"dense={'ON' if RAG_DENSE_ENABLED else 'OFF'}")
    parts.append(f"sparse={'ON' if RAG_SPARSE_ENABLED else 'OFF'}")
    parts.append(f"fusion={'ON' if fusion else 'OFF'}")
    parts.append(f"reranker={'ON' if reranker else 'OFF'}")
    logger.info("流水线配置: %s", " | ".join(parts))

    return pipeline


def get_pipeline() -> RetrievalPipeline:
    global _default_pipeline
    if _default_pipeline is None:
        _default_pipeline = _build_pipeline_from_config()
    return _default_pipeline


def set_pipeline(pipeline: RetrievalPipeline | None):
    """替换全局流水线。传 None 则下次 get_pipeline() 从环境变量重建。"""
    global _default_pipeline
    _default_pipeline = pipeline
