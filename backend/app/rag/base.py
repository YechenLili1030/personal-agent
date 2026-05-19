"""RAG 模块基类 — 所有可插拔组件遵循的接口协议"""

from __future__ import annotations
from typing import Protocol, runtime_checkable

# ── 统一的检索结果结构 ──

class SearchResult:
    """单条检索结果，各 Retriever 必须返回此结构"""
    __slots__ = ("chunk_id", "content", "score", "metadata")

    def __init__(self, chunk_id: str, content: str, score: float = 0.0,
                 metadata: dict | None = None):
        self.chunk_id = chunk_id
        self.content = content
        self.score = score
        self.metadata = metadata or {}

    def to_dict(self) -> dict:
        return {
            "chunk_id": self.chunk_id,
            "content": self.content,
            "score": self.score,
            "metadata": self.metadata,
        }

    @staticmethod
    def from_dict(d: dict) -> SearchResult:
        return SearchResult(
            chunk_id=d.get("chunk_id", ""),
            content=d.get("content", ""),
            score=d.get("score", 0.0),
            metadata=d.get("metadata", {}),
        )


# ── 组件接口 ──

@runtime_checkable
class QueryRewriter(Protocol):
    """查询改写器 — 输入原始 query + 对话历史，输出改写后的 query"""
    async def rewrite(self, query: str, history: list[dict]) -> str:
        ...


@runtime_checkable
class Retriever(Protocol):
    """检索器 — 输入查询文本，输出 SearchResult 列表"""
    async def retrieve(self, query: str, top_k: int, **kwargs) -> list[SearchResult]:
        ...

    @property
    def name(self) -> str:
        ...


@runtime_checkable
class Fusion(Protocol):
    """融合器 — 将多路检索结果合并"""
    def merge(self, result_lists: list[list[SearchResult]], top_k: int) -> list[SearchResult]:
        ...


@runtime_checkable
class Reranker(Protocol):
    """重排序器 — 对检索结果重新打分排序"""
    async def rerank(self, query: str, results: list[SearchResult],
                     top_k: int) -> list[SearchResult]:
        ...
