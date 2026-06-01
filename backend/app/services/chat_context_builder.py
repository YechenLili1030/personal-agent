from __future__ import annotations

import logging
import time

from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import EPISODIC_ENABLED, GRAPH_ENABLED, SEMANTIC_ENABLED
from ..core.prompts import CHAT_SYSTEM_PROMPT
from ..memory import (
    format_semantic_section,
    get_working_memory,
    load_preferences,
    retrieve_episodes,
)
from ..models.user import User
from ..rag import get_pipeline
from .chat_common import count_tokens
from .graph_retrieval import extract_entities_from_chunks, retrieve_graph_context
from .intent import detect_intent

logger = logging.getLogger(__name__)


async def build_context(
    db: AsyncSession,
    session_id: str,
    user_msg: str,
    user_id: str = "",
) -> tuple[list[dict], list[str], str]:
    wm = get_working_memory()

    user = await db.get(User, user_id) if user_id else None
    semantic = load_preferences(user)

    history = await wm.get_window(user_id, session_id, db)
    logger.info("工作记忆: %d 条消息, %d tokens", len(history), count_tokens(history))

    episodes = await retrieve_episodes(user_msg, user_id) if EPISODIC_ENABLED else []

    started_at = time.time()
    intent = await detect_intent(user_msg)
    logger.info("意图识别: %s | %.0fms", intent, (time.time() - started_at) * 1000)

    history_section = _format_history(history)
    episodic_section = _format_episodes(episodes)
    rag_section, graph_section, sources = await _build_retrieval_sections(
        query=user_msg,
        history=history,
        user_id=user_id,
        need_retrieval=intent == "rag",
    )
    semantic_section = format_semantic_section(semantic) if SEMANTIC_ENABLED else ""

    system_content = CHAT_SYSTEM_PROMPT.format(
        semantic_section=semantic_section,
        episodic_section=episodic_section,
        history_section=history_section,
        rag_section=rag_section,
        graph_section=graph_section,
        user_question=user_msg,
    )

    return [
        {"role": "system", "content": system_content},
        {"role": "user", "content": user_msg},
    ], sources, intent


def _format_history(history: list[dict]) -> str:
    if not history:
        return "（无历史对话）"

    lines = ["【历史对话 · 仅供参考 · 不要重复回答以下内容】"]
    for message in history:
        role_label = "用户" if message["role"] == "user" else "助手"
        content = message["content"]
        if len(content) > 500:
            content = content[:500] + "..."
        lines.append(f"{role_label}: {content}")
    return "\n".join(lines)


def _format_episodes(episodes: list[dict]) -> str:
    if not episodes:
        return "（无相关历史片段）"

    lines = ["【以下是与当前问题相关的历史交互片段】"]
    for episode in episodes:
        lines.append(f"- {episode['content']}")
    return "\n".join(lines)


async def _build_retrieval_sections(
    *,
    query: str,
    history: list[dict],
    user_id: str,
    need_retrieval: bool,
) -> tuple[str, str, list[str]]:
    default_rag_section = "（无参考资料，使用自身知识回答）"
    if not need_retrieval:
        return default_rag_section, "", []

    pipeline = get_pipeline()
    history_dicts = [{"role": item["role"], "content": item["content"]} for item in history or []]
    results = await pipeline.run(query=query, history=history_dicts, user_id=user_id)

    graph_section = await _build_graph_section(results, user_id)
    rag_section, sources = _format_rag_results(results)
    return rag_section or default_rag_section, graph_section, sources


async def _build_graph_section(results: list, user_id: str) -> str:
    if not GRAPH_ENABLED or not results:
        return ""

    try:
        entity_names = extract_entities_from_chunks([result.to_dict() for result in results])
        if entity_names:
            return retrieve_graph_context(entity_names, user_id)
    except Exception as exc:
        logger.warning("图谱检索失败: %s", exc)

    return ""


def _format_rag_results(results: list) -> tuple[str, list[str]]:
    if not results:
        return "", []

    docs: dict[str, dict] = {}
    for result in results:
        metadata = result.metadata
        source = metadata.get("filename", "未知")
        if source not in docs:
            docs[source] = {"summary": metadata.get("summary", ""), "chunks": []}
        docs[source]["chunks"].append(result.content)

    sections = []
    for source, info in docs.items():
        header = f"文档《{source}》"
        if info["summary"]:
            header += f"\n摘要: {info['summary']}"
        sections.append(header + "\n" + "\n---\n".join(info["chunks"]))

    return "\n\n".join(sections), list(docs.keys())
