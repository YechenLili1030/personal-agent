import asyncio
import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import async_session, get_db
from ..memory import compress_and_store, get_working_memory
from ..models.chat import Message
from ..models.user import User
from ..services.chat_agent_runner import generate_title, run_chat_agent
from ..services.chat_context_builder import build_context
from ..services.chat_session_service import (
    create_session,
    delete_session,
    get_history,
    get_session,
    list_sessions,
    save_message,
    update_session,
)
from .deps import require_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("/session/create")
async def create_chat_session(
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_user),
):
    title = body.get("title", "新对话")
    mode = body.get("mode", "normal")
    session = await create_session(db, current_user.id, title, mode)
    return {
        "code": 0,
        "data": {
            "session_id": session.id,
            "title": session.title,
            "mode": session.mode,
            "created_at": session.created_at.isoformat() if session.created_at else "",
        },
    }


@router.get("/session/list")
async def list_chat_sessions(
    page: int = 1,
    page_size: int = 20,
    status: str = "",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_user),
):
    items, total = await list_sessions(db, current_user.id, page, page_size, status)
    return {"code": 0, "data": {"items": items, "total": total, "page": page, "page_size": page_size}}


@router.patch("/session/{session_id}")
async def update_chat_session(
    session_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_user),
):
    kwargs = {k: body[k] for k in ("title", "status") if k in body}
    session = await update_session(db, current_user.id, session_id, **kwargs)
    if not session:
        raise HTTPException(404, detail="会话不存在")
    return {"code": 0, "data": {"session_id": session.id, "title": session.title, "status": session.status}}


@router.delete("/session/{session_id}")
async def delete_chat_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_user),
):
    ok = await delete_session(db, current_user.id, session_id)
    if not ok:
        raise HTTPException(404, detail="会话不存在")
    return {"code": 0, "data": {"deleted": True, "session_id": session_id}}


@router.get("/message/{session_id}/history")
async def get_chat_history(
    session_id: str,
    page: int = 1,
    page_size: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_user),
):
    session = await get_session(db, current_user.id, session_id)
    if not session:
        raise HTTPException(404, detail="会话不存在")
    msgs = await get_history(db, current_user.id, session_id, 1000)
    total = len(msgs)
    start = (page - 1) * page_size
    items = msgs[start:start + page_size]
    return {"code": 0, "data": {"items": items, "total": total, "page": page, "page_size": page_size}}


def _sse_event(event_type: str, data) -> str:
    return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/session/{session_id}/stream")
async def stream_chat_message(
    session_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_user),
):
    """SSE stream: client submits one message, server only pushes events back."""
    session = await get_session(db, current_user.id, session_id)
    if not session:
        raise HTTPException(404, detail="会话不存在")

    content = body.get("content", "").strip()
    if not content:
        raise HTTPException(400, detail="消息内容不能为空")

    async def event_stream():
        try:
            wm = get_working_memory()
            await save_message(db, session_id, "user", content)
            await wm.append(current_user.id, session_id, "user", content, db)

            msg_count = (await db.execute(
                select(func.count()).select_from(Message).where(Message.session_id == session_id)
            )).scalar()
            if msg_count <= 2 and session.title == "新对话":
                session.title = await generate_title(content)
                await db.commit()
                yield _sse_event("title", session.title)

            messages, sources, intent = await build_context(db, session_id, content, current_user.id)
            full_response = ""

            async for token in run_chat_agent(messages):
                full_response += token
                yield _sse_event("token", token)

            meta = {"intent": intent}
            if sources:
                meta["sources"] = sources
            await save_message(db, session_id, "assistant", full_response, meta)
            await wm.append(current_user.id, session_id, "assistant", full_response, db)

            from ..core.config import EPISODIC_ENABLED, SEMANTIC_ENABLED
            if EPISODIC_ENABLED or SEMANTIC_ENABLED:
                all_msgs = await get_history(db, current_user.id, session_id)
                if EPISODIC_ENABLED:
                    asyncio.create_task(compress_and_store(current_user.id, session_id, all_msgs))
                if SEMANTIC_ENABLED:
                    asyncio.create_task(_background_semantic_extract(current_user.id, all_msgs))

            yield _sse_event("done", {"sources": sources, "intent": intent})
        except Exception as e:
            logger.exception("SSE chat error")
            yield _sse_event("error", {"message": str(e)})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def _background_semantic_extract(user_id: str, messages: list[dict]):
    from ..memory.semantic import extract_and_update

    async with async_session() as db:
        await extract_and_update(user_id, db, messages)
