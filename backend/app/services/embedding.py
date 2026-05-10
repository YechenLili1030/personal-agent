"""百炼 text-embedding-v4 向量化服务"""

from __future__ import annotations
import logging
from openai import OpenAI
from ..core.config import BAILIAN_API_KEY, BAILIAN_BASE_URL, EMBEDDING_MODEL

logger = logging.getLogger(__name__)

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=BAILIAN_API_KEY, base_url=BAILIAN_BASE_URL)
    return _client


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """批量向量化文本，返回对应 embedding 列表"""
    if not texts:
        return []

    client = _get_client()
    try:
        resp = client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=texts,
        )
        # 按 index 排序确保顺序
        sorted_data = sorted(resp.data, key=lambda d: d.index)
        return [d.embedding for d in sorted_data]
    except Exception as e:
        logger.error("Embedding API 调用失败: %s", e)
        raise


async def embed_single(text: str) -> list[float]:
    """向量化单条文本"""
    embeddings = await embed_texts([text])
    return embeddings[0]
