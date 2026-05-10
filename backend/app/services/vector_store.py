"""ChromaDB 向量存储服务"""

from __future__ import annotations
import logging
from chromadb import PersistentClient
from chromadb.config import Settings
from ..core.config import CHROMA_PERSIST_DIR, CHROMA_COLLECTION

logger = logging.getLogger(__name__)

_client: PersistentClient | None = None


def _get_client() -> PersistentClient:
    global _client
    if _client is None:
        _client = PersistentClient(
            path=CHROMA_PERSIST_DIR,
            settings=Settings(anonymized_telemetry=False),
        )
    return _client


def get_collection():
    client = _get_client()
    return client.get_or_create_collection(name=CHROMA_COLLECTION)


def add_chunks(chunk_ids: list[str], texts: list[str], embeddings: list[list[float]],
               metadatas: list[dict] | None = None):
    """批量添加向量到 ChromaDB"""
    if not chunk_ids:
        return
    collection = get_collection()
    collection.add(
        ids=chunk_ids,
        embeddings=embeddings,
        documents=texts,
        metadatas=metadatas or [{}] * len(chunk_ids),
    )


def delete_by_doc_id(doc_id: str):
    """按文档 ID 删除所有关联 chunk 的向量"""
    collection = get_collection()
    try:
        results = collection.get(where={"doc_id": doc_id})
        if results and results["ids"]:
            collection.delete(ids=results["ids"])
    except Exception as e:
        logger.warning("删除向量失败 (可能集合为空): %s", e)


def query(embedding: list[float], top_k: int = 5) -> list[dict]:
    """向量相似度检索"""
    collection = get_collection()
    results = collection.query(query_embeddings=[embedding], n_results=top_k)
    if not results or not results["ids"] or not results["ids"][0]:
        return []

    out = []
    ids = results["ids"][0]
    docs = results["documents"][0] if results["documents"] else [""] * len(ids)
    metas = results["metadatas"][0] if results["metadatas"] else [{}] * len(ids)
    distances = results["distances"][0] if results["distances"] else [0] * len(ids)

    for i, cid in enumerate(ids):
        out.append({
            "chunk_id": cid,
            "content": docs[i],
            "metadata": metas[i] or {},
            "score": 1 - distances[i] if distances[i] else 0,
        })
    return out
