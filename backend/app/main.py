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
