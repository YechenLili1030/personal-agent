"""语义记忆 — 用户画像与偏好, 存储于 MySQL users.preferences JSON 列"""

from __future__ import annotations
import json
import logging
import time

from openai import OpenAI
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL
from ..core.prompts import SEMANTIC_EXTRACT_PROMPT
from ..models.user import User

logger = logging.getLogger(__name__)

_last_semantic_extract: dict[str, int] = {}
_SEMANTIC_INTERVAL = 4  # 至少新增 4 条消息 (2 轮) 才再次提取


def load_preferences(user: User | None) -> dict:
    """加载用户画像, 返回 dict"""
    if user and user.preferences:
        return dict(user.preferences)
    return {}


def _format_preferences(prefs: dict) -> str:
    """格式化已有画像为可读文本"""
    if not prefs:
        return "（无）"
    lines = []
    for k, v in prefs.items():
        if isinstance(v, list):
            v = ", ".join(str(x) for x in v)
        lines.append(f"- {k}: {v}")
    return "\n".join(lines)


async def extract_and_update(user_id: str, db: AsyncSession,
                             recent_messages: list[dict]) -> dict:
    """从最近对话提取新事实, Upsert 到 users.preferences"""
    prefs = {}
    try:
        user = await db.get(User, user_id)
        if user:
            prefs = load_preferences(user)
    except Exception:
        return {}

    total = len(recent_messages)
    if total < 4:
        return prefs

    # 节流: 距上次提取不足 2 条消息则跳过
    last = _last_semantic_extract.get(user_id, 0)
    if total - last < _SEMANTIC_INTERVAL:
        return prefs

    if len(_last_semantic_extract) > 200:
        _last_semantic_extract.clear()
    _last_semantic_extract[user_id] = total

    # 取最近 8 条消息用于提取
    recent = recent_messages[-8:]
    lines = []
    for m in recent:
        role = "用户" if m.get("role") == "user" else "助手"
        content = m.get("content", "")
        if len(content) > 200:
            content = content[:200] + "..."
        lines.append(f"{role}: {content}")

    prompt = SEMANTIC_EXTRACT_PROMPT.format(
        existing=_format_preferences(prefs),
        conversation="\n".join(lines),
    )

    t0 = time.time()
    try:
        client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)
        resp = client.chat.completions.create(
            model="deepseek-v4-flash",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=400,
            extra_body={"thinking": {"type": "disabled"}},
        )
        raw = (resp.choices[0].message.content or "").strip()
        elapsed = (time.time() - t0) * 1000

        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1]
            if raw.endswith("```"):
                raw = raw[:-3]
            raw = raw.strip()

        data = json.loads(raw)
        items = data.get("items", [])
    except Exception as e:
        logger.warning("语义提取失败: %s | %.0fms", e, (time.time() - t0) * 1000)
        return prefs

    if not items:
        return prefs

    # Upsert
    changed = False
    for item in items:
        key = item.get("key", "").strip()
        value = item.get("value", "").strip()
        action = item.get("action", "set")
        old = item.get("old_value")

        if not key or not value:
            continue

        if action == "update" and old and key in prefs:
            logger.info("语义更新: %s: '%s' → '%s'", key, prefs[key], value)
            prefs[key] = value
            changed = True
        elif key not in prefs or prefs[key] != value:
            logger.info("语义新增: %s = '%s'", key, value)
            prefs[key] = value
            changed = True

    if changed:
        try:
            user = await db.get(User, user_id)
            if user:
                user.preferences = prefs
                await db.commit()
                logger.info("语义记忆已更新: %d 个字段", len(items))
        except Exception as e:
            logger.warning("语义记忆写入失败: %s", e)

    logger.info("语义提取: %d 项 | %.0fms", len(items), elapsed)
    return prefs


def format_semantic_section(prefs: dict) -> str:
    """将用户画像格式化为 system prompt 段落"""
    if not prefs:
        return ""
    lines = ["【用户画像】"]
    for k, v in prefs.items():
        if isinstance(v, list):
            v = ", ".join(str(x) for x in v)
        lines.append(f"- {k}: {v}")
    return "\n".join(lines)
