"""RAG 可插拔模块

Usage:
    from .pipeline import RetrievalPipeline, get_pipeline
    pipeline = get_pipeline()
    results = await pipeline.run(query="...", history=[...], user_id="...")

A/B 测试:
    pipeline = RetrievalPipeline(
        retrievers=[DenseRetriever()],   # 只用稠密检索
        fusion=None,                      # 不用融合
        reranker=None,                    # 不用 rerank
    )
    set_pipeline(pipeline)
"""

from .base import SearchResult
from .pipeline import RetrievalPipeline, get_pipeline, set_pipeline

__all__ = [
    "SearchResult",
    "RetrievalPipeline",
    "get_pipeline",
    "set_pipeline",
]
