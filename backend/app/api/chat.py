import json
import logging
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from ..core.database import get_db, async_session
from ..models.user import User
from ..models.chat import Session, Message
from ..services.auth import get_current_user
from ..services.chat_service import (
    create_session, list_sessions, update_session, delete_session,
    get_history, save_message, build_context, run_chat_agent, generate_title,
)
from .deps import require_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/chat", tags=["chat"])


# =========================== Session REST ===========================

@router.post("/session/create")
async def create_chat_session(
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_user),
):
    title = body.get("title", "新对话")
    mode = body.get("mode", "normal")
    if mode not in ("normal", "rag"):
        raise HTTPException(400, detail="mode 必须为 normal 或 rag")
    session = await create_session(db, current_user.id, title, mode)
    return {
        "code": 0,
        "data": {
            "session_id": session.id, "title": session.title, "mode": session.mode,
            "created_at": session.created_at.isoformat() if session.created_at else "",
        },
    }


@router.get("/session/list")
async def list_chat_sessions(
    page: int = 1, page_size: int = 20, status: str = "",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_user),
):
    items, total = await list_sessions(db, current_user.id, page, page_size, status)
    return {"code": 0, "data": {"items": items, "total": total, "page": page, "page_size": page_size}}


@router.patch("/session/{session_id}")
async def update_chat_session(
    session_id: str, body: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_user),
):
    kwargs = {k: body[k] for k in ("title", "status") if k in body}
    session = await update_session(db, session_id, **kwargs)
    if not session:
        raise HTTPException(404, detail="会话不存在")
    return {"code": 0, "data": {"session_id": session.id, "title": session.title, "status": session.status}}


@router.delete("/session/{session_id}")
async def delete_chat_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_user),
):
    ok = await delete_session(db, session_id)
    if not ok:
        raise HTTPException(404, detail="会话不存在")
    return {"code": 0, "data": {"deleted": True, "session_id": session_id}}


@router.get("/message/{session_id}/history")
async def get_chat_history(
    session_id: str, page: int = 1, page_size: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_user),
):
    msgs = await get_history(db, session_id, 1000)
    total = len(msgs)
    start = (page - 1) * page_size
    items = msgs[start:start + page_size]
    return {"code": 0, "data": {"items": items, "total": total, "page": page, "page_size": page_size}}


# =========================== WebSocket ===========================

@router.websocket("/ws/{session_id}")
async def chat_websocket(ws: WebSocket, session_id: str, token: str = Query(...)):
    """WebSocket 流式对话"""

    # 认证
    async with async_session() as db:
        user = await get_current_user(db, token)
        if not user:
            await ws.close(code=4001, reason="认证失败")
            return

        session = await db.get(Session, session_id)
        if not session:
            await ws.close(code=4004, reason="会话不存在")
            return

    await ws.accept()

    async with async_session() as db:
        # 重新加载 session 到当前 db 上下文，确保后续修改能正常持久化
        session = await db.get(Session, session_id)
        if not session:
            await ws.close(code=4004, reason="会话不存在")
            return

        try:
            while True:
                raw = await ws.receive_text()
                data = json.loads(raw)

                if data.get("type") == "stop":
                    await ws.send_json({"type": "done", "data": {"reason": "stopped"}})
                    continue

                if data.get("type") != "chat":
                    continue

                content = data.get("content", "").strip()
                mode = data.get("mode", session.mode)
                if mode not in ("normal", "rag"):
                    mode = "normal"

                if not content:
                    continue

                # 更新 session mode
                if mode != session.mode:
                    session.mode = mode
                    await db.commit()

                # 保存用户消息
                await save_message(db, session_id, "user", content)

                # 首条消息自动生成标题
                msg_count = (await db.execute(
                    select(func.count()).select_from(Message).where(Message.session_id == session_id)
                )).scalar()
                if msg_count <= 2 and session.title == "新对话":
                    session.title = await generate_title(content)
                    await db.commit()
                    await ws.send_json({"type": "title", "data": session.title})

                # 构建上下文
                messages, sources = await build_context(db, session_id, content, mode, user.id)

                # 流式回复
                full_response = ""

                async for token in run_chat_agent(messages):
                    full_response += token
                    await ws.send_json({"type": "token", "data": token})

                # 保存助手消息
                meta = {"mode": mode}
                if sources:
                    meta["sources"] = sources
                await save_message(db, session_id, "assistant", full_response, meta)

                # 完成
                if sources:
                    await ws.send_json({"type": "sources", "data": sources})
                await ws.send_json({"type": "done", "data": {"sources": sources}})

        except WebSocketDisconnect:
            pass
        except Exception as e:
            logger.exception("WebSocket 错误")
            try:
                await ws.send_json({"type": "error", "data": {"message": str(e)}})
            except Exception:
                pass
