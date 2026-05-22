import logging
from datetime import date, datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..models.user import User
from ..schemas.news import (
    NewsKeywordsUpdate, NewsKeywordsResponse,
    BriefingResponse, BriefingListItem, BriefingListResponse, GenerateRequest,
)
from ..services.news_service import (
    get_user_keywords, update_user_keywords,
    get_briefing_by_date, list_briefings, generate_briefing,
)
from .deps import require_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/news", tags=["news"])


@router.get("/keywords")
async def get_keywords(
    current_user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    keywords = await get_user_keywords(current_user.id, db)
    return {"code": 0, "data": {"keywords": keywords}}


@router.put("/keywords")
async def update_keywords(
    body: NewsKeywordsUpdate,
    current_user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    keywords = await update_user_keywords(current_user.id, body.keywords, db)
    return {"code": 0, "data": {"keywords": keywords}, "message": "关键词已更新"}


@router.get("/briefings")
async def get_briefings(
    current_user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    briefings = await list_briefings(current_user.id, db)
    items = [
        BriefingListItem(
            id=b.id,
            date=b.date.isoformat() if isinstance(b.date, date) else str(b.date),
            title=b.title,
            status=b.status,
            created_at=b.created_at.isoformat() if b.created_at else "",
        )
        for b in briefings
    ]
    return {"code": 0, "data": {"items": [i.model_dump() for i in items], "total": len(items)}}


@router.get("/briefing/{target_date}")
async def get_briefing(
    target_date: str,
    current_user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    briefing = await get_briefing_by_date(current_user.id, target_date, db)
    if not briefing:
        return {"code": 0, "data": None, "message": "该日期暂无简报"}

    return {
        "code": 0,
        "data": {
            "id": briefing.id,
            "date": briefing.date.isoformat() if isinstance(briefing.date, date) else str(briefing.date),
            "title": briefing.title,
            "news_items": briefing.news_items or [],
            "keywords_used": briefing.keywords_used or [],
            "status": briefing.status,
            "created_at": briefing.created_at.isoformat() if briefing.created_at else "",
        },
    }


@router.post("/generate")
async def trigger_generate(
    body: GenerateRequest,
    current_user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    keywords = await get_user_keywords(current_user.id, db)
    if not keywords:
        raise HTTPException(400, detail="请先设置新闻关键词")

    # 验证日期格式
    try:
        datetime.strptime(body.date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(400, detail="日期格式错误，应为 YYYY-MM-DD")

    briefing = await generate_briefing(current_user.id, keywords, body.date, db)

    return {
        "code": 0,
        "data": {
            "id": briefing.id,
            "date": briefing.date.isoformat() if isinstance(briefing.date, date) else str(briefing.date),
            "title": briefing.title,
            "news_items": briefing.news_items or [],
            "keywords_used": briefing.keywords_used or [],
            "status": briefing.status,
            "error_msg": briefing.error_msg,
            "created_at": briefing.created_at.isoformat() if briefing.created_at else "",
        },
    }
