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

    logger.info("PersonalAgent 启动完成")
    yield
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


@app.get("/")
async def root():
    return {"message": "PersonalAgent API is running"}
