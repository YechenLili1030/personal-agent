"""BM25 稀疏检索 — 关键词匹配，与 ChromaDB 稠密检索互补"""

from __future__ import annotations
import json
import logging
import math
import os
from collections import defaultdict

import jieba
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import BM25_INDEX_PATH

logger = logging.getLogger(__name__)


class BM25Store:
    """轻量级 BM25 内存索引，数据来源为 MySQL doc_chunks 表"""

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.corpus: list[dict] = []       # [{"id", "tokens", "content", "metadata"}, ...]
        self.doc_freqs: dict[str, int] = defaultdict(int)
        self._idf: dict[str, float] = {}
        self.avgdl: float = 0.0

    # ── tokenizer ────────────────────────────────────────

    @staticmethod
    def tokenize(text: str) -> list[str]:
        """jieba 分词，过滤空白和单字 token"""
        tokens = list(jieba.cut(text))
        result = []
        for t in tokens:
            t = t.strip().lower()
            if t and len(t) > 1:
                result.append(t)
        return result

    # ── build index ──────────────────────────────────────

    def index(self, chunks: list[dict]):
        """
        从 chunk 列表构建 BM25 索引。
        chunks: [{"id": str, "content": str, "metadata": dict}, ...]
        """
        self.corpus = []
        self.doc_freqs = defaultdict(int)

        for chunk in chunks:
            tokens = self.tokenize(chunk["content"])
            self.corpus.append({
                "id": chunk["id"],
                "tokens": tokens,
                "content": chunk["content"],
                "metadata": chunk.get("metadata", {}),
            })
            for term in set(tokens):
                self.doc_freqs[term] += 1

        total_len = sum(len(d["tokens"]) for d in self.corpus)
        self.avgdl = total_len / len(self.corpus) if self.corpus else 1.0
        self._compute_idf()
        logger.info("BM25 索引已构建 | docs=%d | avgdl=%.1f", len(self.corpus), self.avgdl)

    def _compute_idf(self):
        self._idf = {}
        for term, df in self.doc_freqs.items():
            self._idf[term] = math.log(
                (len(self.corpus) - df + 0.5) / (df + 0.5) + 1
            )

    # ── search ───────────────────────────────────────────

    def search(self, query: str, top_k: int = 20, user_id: str | None = None) -> list[dict]:
        """BM25 检索，可选按 user_id 过滤。返回 [{"chunk_id", "content", "metadata", "score"}, ...]"""
        if not self.corpus:
            return []

        query_tokens = self.tokenize(query)
        if not query_tokens:
            return []

        scores: list[tuple[float, int]] = []
        for i, doc in enumerate(self.corpus):
            if user_id and doc["metadata"].get("user_id") != user_id:
                continue
            score = self._score(query_tokens, doc)
            if score > 0:
                scores.append((score, i))

        scores.sort(key=lambda x: x[0], reverse=True)
        top = scores[:top_k]

        results = []
        for score, idx in top:
            doc = self.corpus[idx]
            results.append({
                "chunk_id": doc["id"],
                "content": doc["content"],
                "metadata": doc["metadata"],
                "score": score,
            })
        return results

    def _score(self, query_tokens: list[str], doc: dict) -> float:
        doc_len = len(doc["tokens"])
        tf_map = defaultdict(int)
        for t in doc["tokens"]:
            tf_map[t] += 1

        total = 0.0
        for term in query_tokens:
            idf = self._idf.get(term)
            if idf is None:
                continue
            tf = tf_map.get(term, 0)
            if tf == 0:
                continue
            numerator = tf * (self.k1 + 1)
            denominator = tf + self.k1 * (1 - self.b + self.b * doc_len / self.avgdl)
            total += idf * numerator / denominator
        return total

    # ── persistence ──────────────────────────────────────

    def save(self, path: str):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        data = {
            "k1": self.k1,
            "b": self.b,
            "corpus": [
                {"id": d["id"], "content": d["content"], "metadata": d["metadata"]}
                for d in self.corpus
            ],
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info("BM25 索引已保存至 %s (%d docs)", path, len(self.corpus))

    @classmethod
    def load(cls, path: str) -> "BM25Store":
        store = cls()
        if not os.path.exists(path):
            logger.info("BM25 索引文件不存在，将在首次文档入库时构建: %s", path)
            return store
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        store.k1 = data.get("k1", 1.5)
        store.b = data.get("b", 0.75)
        store.index(data["corpus"])
        logger.info("BM25 索引已从 %s 加载", path)
        return store


# ═══════════════════════ 单例 ═══════════════════════

_store: BM25Store | None = None
_index_path: str | None = None


def get_bm25_store() -> BM25Store:
    """获取 BM25 单例（未初始化时返回空索引）"""
    global _store
    if _store is None:
        _store = BM25Store()
    return _store


def init_bm25_store(path: str) -> BM25Store:
    """启动时从文件加载 BM25 索引"""
    global _store, _index_path
    _index_path = path
    _store = BM25Store.load(path)
    return _store


async def rebuild_bm25_index(db: AsyncSession):
    """从 MySQL doc_chunks + knowledge_docs 表全量重建 BM25 索引（含 user_id）"""
    from ..models.knowledge import DocChunk, KnowledgeDoc

    result = await db.execute(
        select(DocChunk, KnowledgeDoc.user_id)
        .join(KnowledgeDoc, DocChunk.doc_id == KnowledgeDoc.id)
    )
    rows = result.all()

    store = get_bm25_store()
    store.index([
        {
            "id": row.DocChunk.id,
            "content": row.DocChunk.content,
            "metadata": {
                "doc_id": row.DocChunk.doc_id,
                "chunk_index": row.DocChunk.chunk_index,
                "filename": (row.DocChunk.chunk_metadata or {}).get("source", ""),
                "summary": (row.DocChunk.chunk_metadata or {}).get("summary", ""),
                "file_type": (row.DocChunk.chunk_metadata or {}).get("file_type", ""),
                "user_id": row.user_id,
            },
        }
        for row in rows
    ])

    if _index_path:
        store.save(_index_path)
