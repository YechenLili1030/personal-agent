import os
import time
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from .core.config import UPLOAD_DIR, CHROMA_PERSIST_DIR, BM25_INDEX_PATH
from .core.logging_config import setup_logging
from .api.auth import router as auth_router
from .api.knowledge import router as knowledge_router
from .api.chat import router as chat_router
from .api.news import router as news_router

setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(application: FastAPI):
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    os.makedirs(CHROMA_PERSIST_DIR, exist_ok=True)

    from .services.bm25_store import init_bm25_store
    init_bm25_store(BM25_INDEX_PATH)

    # MCP 客户端初始化 + 加载外部工具
    from .mcp.client import init_mcp_client
    from .tools import refresh_all_tools
    await init_mcp_client()
    await refresh_all_tools()

    # RAG 流水线初始化（打印组件配置）
    from .rag import get_pipeline
    get_pipeline()

    # 数据库迁移：确保 daily_briefings 表存在
    try:
        from .core.database import engine as async_engine
        from sqlalchemy import text as sa_text
        async with async_engine.connect() as conn:
            await conn.execute(sa_text(
                "CREATE TABLE IF NOT EXISTS daily_briefings ("
                "id CHAR(36) PRIMARY KEY, "
                "user_id CHAR(36) NOT NULL, "
                "date DATE NOT NULL, "
                "title VARCHAR(256) DEFAULT NULL, "
                "news_items JSON DEFAULT NULL, "
                "keywords_used JSON DEFAULT NULL, "
                "status VARCHAR(20) DEFAULT 'pending', "
                "error_msg TEXT DEFAULT NULL, "
                "created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, "
                "updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP, "
                "UNIQUE KEY uq_user_date (user_id, date), "
                "INDEX idx_user_id (user_id)"
                ")"
            ))
            # 尝试为 users 表添加 news_keywords 列
            try:
                await conn.execute(sa_text(
                    "ALTER TABLE users ADD COLUMN news_keywords JSON DEFAULT NULL"
                ))
                await conn.commit()
                logger.info("数据库迁移: users.news_keywords 列已添加")
            except Exception:
                logger.debug("news_keywords 列可能已存在，跳过迁移")
            await conn.commit()
        logger.info("数据库迁移: daily_briefings 表已创建")
    except Exception as e:
        logger.debug("daily_briefings 表可能已存在，跳过迁移: %s", e)

    # 数据库迁移：确保 knowledge_docs 有 graph_status 列
    try:
        from .core.database import engine as async_engine
        from sqlalchemy import text as sa_text
        async with async_engine.connect() as conn:
            await conn.execute(sa_text(
                "ALTER TABLE knowledge_docs ADD COLUMN graph_status VARCHAR(16) DEFAULT NULL"
            ))
            await conn.commit()
        logger.info("数据库迁移: graph_status 列已添加")
    except Exception:
        logger.debug("graph_status 列可能已存在，跳过迁移")

    # 新闻简报定时任务
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.triggers.cron import CronTrigger
    from .core.config import NEWS_CRON_HOUR, NEWS_CRON_MINUTE

    scheduler = AsyncIOScheduler()

    async def daily_news_job():
        """每天定时为所有设置关键词的用户生成新闻简报。"""
        from datetime import date, timedelta
        from .core.database import async_session as _async_session
        from .services.news_service import generate_briefing, get_user_keywords

        yesterday = (date.today() - timedelta(days=1)).isoformat()
        async with _async_session() as _db:
            from .models.user import User
            from sqlalchemy import select
            users = (await _db.execute(select(User))).scalars().all()
            for user in users:
                try:
                    keywords = await get_user_keywords(user.id, _db)
                    if keywords:
                        await generate_briefing(user.id, keywords, yesterday, _db)
                except Exception as e:
                    logger.warning("用户 %s 简报生成失败: %s", user.id, e)

    scheduler.add_job(
        daily_news_job,
        CronTrigger(hour=NEWS_CRON_HOUR, minute=NEWS_CRON_MINUTE),
        id="daily_news_briefing",
        name="每日新闻简报生成",
    )
    scheduler.start()
    logger.info("新闻简报定时任务已启动: cron=%d:%02d", NEWS_CRON_HOUR, NEWS_CRON_MINUTE)

    logger.info("PersonalAgent 启动完成")
    yield
    scheduler.shutdown(wait=False)
    logger.info("PersonalAgent 关闭")


app = FastAPI(title="PersonalAgent API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 请求日志中间件
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    elapsed = (time.time() - start) * 1000
    logger.info("%s %s → %d (%.0fms)",
                request.method, request.url.path, response.status_code, elapsed)
    return response


app.include_router(auth_router)
app.include_router(knowledge_router)
app.include_router(chat_router)
app.include_router(news_router)


@app.get("/")
async def root():
    return {"message": "PersonalAgent API is running"}
