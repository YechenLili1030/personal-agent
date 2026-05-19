"""情景记忆 — ChromaDB 独立集合, 用户隔离, 稠密检索"""

from __future__ import annotations
import json
import logging
import time
import uuid
from datetime import datetime

from openai import OpenAI
from chromadb import PersistentClient
from chromadb.config import Settings

from ..core.prompts import EPISODE_PROMPT
from ..core.config import (
    CHROMA_PERSIST_DIR,
    DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL,
    EPISODIC_TOP_K, EPISODIC_MIN_TURNS, EPISODIC_MIN_SCORE,
)
from ..services.embedding import embed_single

logger = logging.getLogger(__name__)

EPISODIC_COLLECTION = "episodic_memory"
EPISODIC_COMPRESS_MSG = 12  # 取最近 12 条消息压缩

_client: PersistentClient | None = None
_embed_client: OpenAI | None = None


def _get_chroma() -> PersistentClient:
    global _client
    if _client is None:
        _client = PersistentClient(
            path=CHROMA_PERSIST_DIR,
            settings=Settings(anonymized_telemetry=False),
        )
    return _client


def _get_episodic_collection():
    return _get_chroma().get_or_create_collection(
        name=EPISODIC_COLLECTION,
        metadata={"hnsw:space": "cosine"},
    )


# ═══════════════════════ 检索 ═══════════════════════

async def retrieve_episodes(query: str, user_id: str,
                            top_k: int = EPISODIC_TOP_K) -> list[dict]:
    """稠密检索 top_k 个相关历史片段"""
    t0 = time.time()
    try:
        query_emb = await embed_single(query)
        collection = _get_episodic_collection()
        results = collection.query(
            query_embeddings=[query_emb],
            n_results=top_k,
            where={"user_id": user_id},
        )
    except Exception as e:
        logger.warning("情景记忆检索失败: %s", e)
        return []

    elapsed = (time.time() - t0) * 1000
    if not results or not results["ids"] or not results["ids"][0]:
        return []

    episodes = []
    ids = results["ids"][0]
    docs = results["documents"][0] if results["documents"] else [""] * len(ids)
    metas = results["metadatas"][0] if results["metadatas"] else [{}] * len(ids)
    distances = results["distances"][0] if results["distances"] else [0] * len(ids)

    for i, eid in enumerate(ids):
        score = 1 - distances[i] if distances[i] else 0
        if score < EPISODIC_MIN_SCORE:
            continue
        episodes.append({
            "episode_id": eid,
            "content": docs[i],
            "metadata": metas[i] or {},
            "score": score,
        })

    logger.info("情景记忆检索: '%s' → %d 条 | %.0fms",
                query[:40], len(episodes), elapsed)
    return episodes


# ═══════════════════════ 存储 ═══════════════════════

async def store_episode(user_id: str, session_id: str, title: str,
                        summary: str, message_count: int = 0):
    """将 episode 写入 ChromaDB"""
    episode_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    embedding = await embed_single(summary)

    try:
        collection = _get_episodic_collection()
        collection.add(
            ids=[episode_id],
            embeddings=[embedding],
            documents=[summary],
            metadatas=[{
                "user_id": user_id,
                "session_id": session_id,
                "title": title,
                "message_count": message_count,
                "created_at": now,
            }],
        )
        logger.info("情景记忆已存储: title='%s' msgs=%d", title, message_count)
    except Exception as e:
        logger.warning("情景记忆存储失败: %s", e)


# ═══════════════════════ 压缩 ═══════════════════════

# 节流: 记录每个会话上次压缩时的消息数，避免每轮都重复压缩
_last_compressed: dict[str, int] = {}
_COMPRESS_INTERVAL = 4  # 至少新增 4 条消息 (2 轮) 才再次压缩

async def compress_and_store(user_id: str, session_id: str,
                             messages: list[dict]) -> bool:
    """判断是否值得存储，是则压缩并写入情景记忆"""
    total = len(messages)
    if total < EPISODIC_MIN_TURNS:
        return False

    # 节流: 距上次压缩不足 4 条消息则跳过
    last = _last_compressed.get(session_id, 0)
    if total - last < _COMPRESS_INTERVAL:
        return False

    # 防止内存泄漏: 超过 200 个会话记录时清空
    if len(_last_compressed) > 200:
        _last_compressed.clear()

    _last_compressed[session_id] = total
    recent = messages[-EPISODIC_COMPRESS_MSG:]
    lines = []
    for m in recent:
        role = "用户" if m.get("role") == "user" else "助手"
        content = m.get("content", "")
        if len(content) > 300:
            content = content[:300] + "..."
        lines.append(f"{role}: {content}")

    prompt = EPISODE_PROMPT.format(conversation="\n".join(lines))

    t0 = time.time()
    try:
        client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)
        resp = client.chat.completions.create(
            model="deepseek-v4-flash",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=300,
            extra_body={"thinking": {"type": "disabled"}},
        )
        raw = (resp.choices[0].message.content or "").strip()
        elapsed = (time.time() - t0) * 1000

        # 清理 markdown 包装
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1]
            if raw.endswith("```"):
                raw = raw[:-3]
            raw = raw.strip()

        data = json.loads(raw)
        title = data.get("title", "对话片段")
        summary = data.get("summary", raw)

        await store_episode(user_id, session_id, title, summary, len(messages))
        logger.info("情景压缩完成: '%s' | %.0fms", title, elapsed)
        return True
    except Exception as e:
        logger.warning("情景压缩失败: %s | %.0fms", e, (time.time() - t0) * 1000)
        return False
