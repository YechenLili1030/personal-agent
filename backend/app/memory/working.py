"""工作记忆 — Redis 热缓存 + MySQL 持久备份，按 token 数滑动窗口"""

from __future__ import annotations
import json
import logging
from datetime import datetime

import redis.asyncio as aioredis
from redis.exceptions import RedisError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from tiktoken import encoding_for_model

from ..core.config import (
    REDIS_URL, REDIS_PASSWORD,
    WORKING_MEMORY_MAX_TOKENS, WORKING_MEMORY_REDIS_TTL,
)

logger = logging.getLogger(__name__)

_enc = encoding_for_model("gpt-4")  # cl100k_base

# ── Redis 连接 (惰性初始化) ──

_redis: aioredis.Redis | None = None
_redis_available: bool | None = None  # None=未检测, True=可用, False=不可用


def _get_redis() -> aioredis.Redis | None:
    global _redis
    if _redis is None:
        try:
            _redis = aioredis.Redis.from_url(
                REDIS_URL,
                password=REDIS_PASSWORD or None,
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2,
            )
        except Exception:
            return None
    return _redis


async def _check_redis() -> bool:
    global _redis_available
    if _redis_available is not None:
        return _redis_available
    r = _get_redis()
    if r is None:
        _redis_available = False
        return False
    try:
        await r.ping()
        _redis_available = True
        logger.info("Redis 已连接")
    except Exception:
        _redis_available = False
        logger.warning("Redis 不可用，工作记忆降级为 MySQL")
    return _redis_available


def _redis_key(user_id: str, session_id: str) -> str:
    return f"wm:{user_id}:{session_id}"


# ── Token 计数 ──

def _count_tokens(messages: list[dict]) -> int:
    total = 0
    for m in messages:
        total += len(_enc.encode(m.get("content", "") or ""))
    return total


def _trim_by_tokens(messages: list[dict], max_tokens: int) -> list[dict]:
    """从头部裁剪，保留尾部不超过 max_tokens 的消息"""
    if not messages:
        return []
    total = _count_tokens(messages)
    if total <= max_tokens:
        return messages
    # 从头部逐条移除
    result = list(messages)
    while result and _count_tokens(result) > max_tokens:
        result.pop(0)
    # 至少保留最后一条
    if not result and messages:
        result = [messages[-1]]
    return result


# ── Redis 读写 ──

async def _redis_load(user_id: str, session_id: str) -> list[dict] | None:
    if not await _check_redis():
        return None
    try:
        r = _get_redis()
        raw = await r.get(_redis_key(user_id, session_id))
        if raw:
            return json.loads(raw)
    except RedisError as e:
        logger.debug("Redis 读取失败: %s", e)
    return None


async def _redis_save(user_id: str, session_id: str, messages: list[dict]):
    if not await _check_redis():
        return
    try:
        r = _get_redis()
        key = _redis_key(user_id, session_id)
        await r.set(key, json.dumps(messages, ensure_ascii=False), ex=WORKING_MEMORY_REDIS_TTL)
    except RedisError as e:
        logger.debug("Redis 写入失败: %s", e)


# ── MySQL 读取 ──

async def _mysql_load(db: AsyncSession, session_id: str) -> list[dict]:
    from ..models.chat import Message
    rows = (await db.execute(
        select(Message)
        .where(Message.session_id == session_id)
        .order_by(Message.created_at.asc())
    )).scalars().all()
    return [{
        "role": m.role,
        "content": m.content,
        "metadata": m.msg_metadata,
        "created_at": m.created_at.isoformat() if m.created_at else "",
    } for m in rows]


# ── 公共 API ──

class WorkingMemory:
    """工作记忆管理器

    ┌─ 读取: Redis → 降级 MySQL → 回填 Redis
    └─ 写入: MySQL 持久化 + Redis 热缓存 (8K token 窗口)
    """

    def __init__(self, max_tokens: int = WORKING_MEMORY_MAX_TOKENS):
        self.max_tokens = max_tokens

    async def get_window(self, user_id: str, session_id: str,
                         db: AsyncSession) -> list[dict]:
        """获取当前会话的工作记忆窗口（按 token 裁剪）"""
        messages = None

        # 1. 优先 Redis
        messages = await _redis_load(user_id, session_id)

        # 2. 降级 MySQL
        if messages is None:
            messages = await _mysql_load(db, session_id)
            # 回填 Redis
            if messages:
                trimmed = _trim_by_tokens(messages, self.max_tokens)
                await _redis_save(user_id, session_id, trimmed)

        return _trim_by_tokens(messages, self.max_tokens)

    async def append(self, user_id: str, session_id: str,
                     role: str, content: str, db: AsyncSession):
        """追加一条消息并更新 Redis 缓存"""
        msg = {
            "role": role,
            "content": content,
            "created_at": datetime.utcnow().isoformat(),
        }

        # Redis 中追加 + 裁剪
        existing = await _redis_load(user_id, session_id)
        if existing is not None:
            existing.append(msg)
            trimmed = _trim_by_tokens(existing, self.max_tokens)
            await _redis_save(user_id, session_id, trimmed)
            return trimmed

        # Redis 不可用: 直接从 MySQL 加载后回填
        messages = await _mysql_load(db, session_id)
        if messages:
            trimmed = _trim_by_tokens(messages, self.max_tokens)
            await _redis_save(user_id, session_id, trimmed)
            return trimmed
        return [msg]

    async def expire(self, user_id: str, session_id: str):
        """会话结束时清除 Redis 缓存"""
        if not await _check_redis():
            return
        try:
            r = _get_redis()
            await r.delete(_redis_key(user_id, session_id))
        except RedisError:
            pass


# ── 全局单例 ──

_wm: WorkingMemory | None = None


def get_working_memory() -> WorkingMemory:
    global _wm
    if _wm is None:
        _wm = WorkingMemory()
    return _wm
