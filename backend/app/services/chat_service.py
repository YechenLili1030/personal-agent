"""对话核心服务 — DeepSeek 流式调用 + RAG 检索 + 上下文管理"""

from __future__ import annotations
import json
import logging
import time
from typing import AsyncGenerator
from langchain_openai import ChatOpenAI
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete as sa_delete
from tiktoken import encoding_for_model

from ..core.config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, CHAT_MODEL
from ..core.prompts import CHAT_SYSTEM_PROMPT, TITLE_PROMPT
from ..models.chat import Session, Message
from ..tools import ALL_TOOLS
from .embedding import embed_single
from .vector_store import query as vector_query

logger = logging.getLogger(__name__)

CONTEXT_WINDOW = 20
RAG_TOP_K = 5

_enc = encoding_for_model("gpt-4")  # cl100k_base, 通用估算


def _count_tokens(messages: list[dict]) -> int:
    total = 0
    for m in messages:
        total += len(_enc.encode(m.get("content", "") or ""))
    return total


def _build_llm(temperature: float = 0.7, max_tokens: int = 4096) -> ChatOpenAI:
    return ChatOpenAI(
        model=CHAT_MODEL,
        temperature=temperature,
        max_tokens=max_tokens,
        api_key=DEEPSEEK_API_KEY,
        base_url=DEEPSEEK_BASE_URL,
    )


# =========================== Session ===========================

async def create_session(db: AsyncSession, user_id: str, title: str = "新对话", mode: str = "normal") -> Session:
    session = Session(user_id=user_id, title=title, mode=mode)
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


async def list_sessions(db: AsyncSession, user_id: str, page: int = 1, page_size: int = 20,
                        status: str = "") -> tuple[list[dict], int]:
    q = select(Session).where(Session.user_id == user_id)
    cq = select(func.count()).select_from(Session).where(Session.user_id == user_id)
    if status:
        q = q.where(Session.status == status)
        cq = cq.where(Session.status == status)
    total = (await db.execute(cq)).scalar()
    rows = (await db.execute(
        q.order_by(Session.updated_at.desc()).offset((page - 1) * page_size).limit(page_size)
    )).scalars().all()

    items = []
    for s in rows:
        cnt = (await db.execute(
            select(func.count()).select_from(Message).where(Message.session_id == s.id)
        )).scalar()
        items.append({
            "session_id": s.id, "title": s.title, "mode": s.mode,
            "message_count": cnt,
            "created_at": s.created_at.isoformat() if s.created_at else "",
            "updated_at": s.updated_at.isoformat() if s.updated_at else "",
        })
    return items, total


async def update_session(db: AsyncSession, session_id: str, **kwargs) -> Session | None:
    session = await db.get(Session, session_id)
    if not session:
        return None
    for k, v in kwargs.items():
        if v is not None and hasattr(session, k):
            setattr(session, k, v)
    await db.commit()
    return session


async def delete_session(db: AsyncSession, session_id: str) -> bool:
    session = await db.get(Session, session_id)
    if not session:
        return False
    await db.execute(sa_delete(Message).where(Message.session_id == session_id))
    await db.delete(session)
    await db.commit()
    return True


# =========================== Messages ===========================

async def get_history(db: AsyncSession, session_id: str, limit: int = 50) -> list[dict]:
    rows = (await db.execute(
        select(Message).where(Message.session_id == session_id)
        .order_by(Message.created_at.asc()).limit(limit)
    )).scalars().all()
    return [{
        "message_id": m.id, "role": m.role, "content": m.content,
        "metadata": m.msg_metadata, "created_at": m.created_at.isoformat() if m.created_at else "",
    } for m in rows]


async def save_message(db: AsyncSession, session_id: str, role: str, content: str,
                       metadata: dict | None = None) -> Message:
    msg = Message(session_id=session_id, role=role, content=content, msg_metadata=metadata)
    db.add(msg)
    await db.commit()
    await db.refresh(msg)
    return msg


# =========================== Context ===========================

async def build_context(db: AsyncSession, session_id: str, user_msg: str, mode: str) -> tuple[list[dict], list[str]]:
    """将所有上下文打包到 system prompt，返回 messages + 来源文件名列表。"""
    history = await get_history(db, session_id, CONTEXT_WINDOW)

    # ━━━ 历史对话 ━━━
    if history:
        lines = ["【历史对话 · 仅供参考 · 不要重复回答以下内容】"]
        for m in history[-CONTEXT_WINDOW:]:
            role_label = "用户" if m["role"] == "user" else "助手"
            content = m["content"][:500] + "..." if len(m["content"]) > 500 else m["content"]
            lines.append(f"{role_label}: {content}")
        history_section = "\n".join(lines)
    else:
        history_section = "（无历史对话）"

    # ━━━ RAG 检索 ━━━
    rag_section = "（无参考资料，使用自身知识回答）"
    sources: list[str] = []
    if mode == "rag":
        try:
            query_emb = await embed_single(user_msg)
            results = vector_query(query_emb, top_k=RAG_TOP_K)
            logger.info("RAG 检索: query='%s' -> %d 条", user_msg[:60], len(results))
            if results:
                docs: dict[str, dict] = {}
                for r in results:
                    meta = r.get("metadata", {})
                    src = meta.get("filename", "未知")
                    if src not in docs:
                        docs[src] = {"summary": meta.get("summary", ""), "chunks": []}
                    docs[src]["chunks"].append(r["content"])

                sources = list(docs.keys())
                parts = []
                for src, info in docs.items():
                    header = f"文档「{src}」"
                    if info["summary"]:
                        header += f"\n摘要: {info['summary']}"
                    parts.append(header + "\n" + "\n---\n".join(info["chunks"]))
                rag_section = "\n\n".join(parts)
        except Exception as e:
            logger.warning("RAG 检索失败: %s", e)

    # ━━━ 组装 ━━━
    system_content = CHAT_SYSTEM_PROMPT.format(
        history_section=history_section,
        rag_section=rag_section,
        user_question=user_msg,
    )

    return [{"role": "system", "content": system_content}, {"role": "user", "content": user_msg}], sources


# =========================== Streaming with Tools ===========================

MAX_TOOL_ITERATIONS = 5
TOOL_NAME_MAP = {t.name: t for t in ALL_TOOLS}


async def run_chat_agent(messages: list[dict]) -> AsyncGenerator[str, None]:
    """带工具调用的流式对话，ReAct 循环自动处理多轮工具交互。"""
    llm = _build_llm().bind_tools(ALL_TOOLS)
    t0 = time.time()
    total_input = 0
    total_output = 0

    for iteration in range(MAX_TOOL_ITERATIONS):
        collected_content = ""
        tool_calls: list[dict] = []

        for chunk in llm.stream([(m["role"], m["content"]) for m in messages]):
            if chunk.content:
                collected_content += chunk.content
                yield chunk.content

            if chunk.tool_call_chunks:
                for tc_chunk in chunk.tool_call_chunks:
                    idx = tc_chunk.get("index", 0)
                    while len(tool_calls) <= idx:
                        tool_calls.append({"name": "", "args": ""})
                    if tc_chunk.get("name"):
                        tool_calls[idx]["name"] += tc_chunk["name"]
                    if tc_chunk.get("args"):
                        tool_calls[idx]["args"] += tc_chunk["args"]

        total_input += _count_tokens(messages)
        total_output += _count_tokens([{"role": "assistant", "content": collected_content}])

        if not tool_calls:
            break

        # 中间轮：执行工具，结果注入上下文继续生成
        tool_results = []
        for tc in tool_calls:
            name = tc["name"].strip()
            fn = TOOL_NAME_MAP.get(name)
            if not fn:
                logger.warning("未知工具: %s", name)
                continue
            try:
                args = json.loads(tc["args"]) if tc["args"].strip() else {}
                result = fn.invoke(args)
                tool_results.append(f"[工具: {name}]\n{result}")
                logger.info("工具调用: %s(%s) → %s", name, args, str(result)[:120])
            except Exception as e:
                logger.error("工具执行失败 %s: %s", name, e)

        messages.append({"role": "assistant", "content": collected_content or " "})
        if tool_results:
            messages.append({"role": "user", "content": "工具返回结果:\n" + "\n\n".join(tool_results)})
        else:
            break

    elapsed = (time.time() - t0) * 1000
    total = total_input + total_output
    logger.info("调用完成 | model=%s | rounds=%d | input=%dt output=%dt total=%dt | %.0fms",
                CHAT_MODEL, iteration + 1, total_input, total_output, total, elapsed)


# =========================== Title generation ===========================

async def generate_title(user_msg: str) -> str:
    t0 = time.time()
    try:
        llm = _build_llm(temperature=0.3, max_tokens=30)
        resp = llm.invoke(TITLE_PROMPT.format(text=user_msg))
        title = resp.content.strip()
        elapsed = (time.time() - t0) * 1000
        logger.info("标题生成 | %s | %.0fms", title, elapsed)
        return title
    except Exception as e:
        logger.warning("标题生成失败: %s", e)
        return user_msg[:20]
