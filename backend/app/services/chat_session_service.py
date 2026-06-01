from __future__ import annotations

from sqlalchemy import delete as sa_delete
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.chat import Message, Session


async def get_session(db: AsyncSession, user_id: str, session_id: str) -> Session | None:
    return (await db.execute(
        select(Session).where(Session.id == session_id, Session.user_id == user_id)
    )).scalar_one_or_none()


async def create_session(
    db: AsyncSession,
    user_id: str,
    title: str = "新对话",
    mode: str = "normal",
) -> Session:
    session = Session(user_id=user_id, title=title, mode=mode)
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


async def list_sessions(
    db: AsyncSession,
    user_id: str,
    page: int = 1,
    page_size: int = 20,
    status: str = "",
) -> tuple[list[dict], int]:
    query = select(Session).where(Session.user_id == user_id)
    count_query = select(func.count()).select_from(Session).where(Session.user_id == user_id)

    if status:
        query = query.where(Session.status == status)
        count_query = count_query.where(Session.status == status)

    total = (await db.execute(count_query)).scalar()
    sessions = (await db.execute(
        query.order_by(Session.updated_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )).scalars().all()

    items = []
    for session in sessions:
        message_count = (await db.execute(
            select(func.count()).select_from(Message).where(Message.session_id == session.id)
        )).scalar()
        items.append({
            "session_id": session.id,
            "title": session.title,
            "mode": session.mode,
            "message_count": message_count,
            "created_at": session.created_at.isoformat() if session.created_at else "",
            "updated_at": session.updated_at.isoformat() if session.updated_at else "",
        })

    return items, total


async def update_session(
    db: AsyncSession,
    user_id: str,
    session_id: str,
    **kwargs,
) -> Session | None:
    session = await get_session(db, user_id, session_id)
    if not session:
        return None

    for key, value in kwargs.items():
        if value is not None and hasattr(session, key):
            setattr(session, key, value)

    await db.commit()
    return session


async def delete_session(db: AsyncSession, user_id: str, session_id: str) -> bool:
    session = await get_session(db, user_id, session_id)
    if not session:
        return False

    await db.execute(sa_delete(Message).where(Message.session_id == session_id))
    await db.delete(session)
    await db.commit()
    return True


async def get_history(
    db: AsyncSession,
    user_id: str,
    session_id: str,
    limit: int = 50,
) -> list[dict]:
    session = await get_session(db, user_id, session_id)
    if not session:
        return []

    messages = (await db.execute(
        select(Message)
        .where(Message.session_id == session_id)
        .order_by(Message.created_at.asc())
        .limit(limit)
    )).scalars().all()

    return [{
        "message_id": message.id,
        "role": message.role,
        "content": message.content,
        "metadata": message.msg_metadata,
        "created_at": message.created_at.isoformat() if message.created_at else "",
    } for message in messages]


async def save_message(
    db: AsyncSession,
    session_id: str,
    role: str,
    content: str,
    metadata: dict | None = None,
) -> Message:
    message = Message(
        session_id=session_id,
        role=role,
        content=content,
        msg_metadata=metadata,
    )
    db.add(message)
    await db.commit()
    await db.refresh(message)
    return message
