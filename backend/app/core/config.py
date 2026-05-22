import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# 项目根目录
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent

# MySQL
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "mikasa2001")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_NAME = os.getenv("DB_NAME", "personal_agent")

DATABASE_URL = f"mysql+aiomysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4"
DATABASE_URL_SYNC = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4"

# Redis — 工作记忆热缓存
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "0"))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "")
REDIS_URL = os.getenv("REDIS_URL", f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}")

# 工作记忆
WORKING_MEMORY_MAX_TOKENS = int(os.getenv("WORKING_MEMORY_MAX_TOKENS", "8000"))
WORKING_MEMORY_REDIS_TTL = int(os.getenv("WORKING_MEMORY_REDIS_TTL", "1800"))

# 情景记忆
EPISODIC_TOP_K = int(os.getenv("EPISODIC_TOP_K", "3"))
EPISODIC_MIN_TURNS = int(os.getenv("EPISODIC_MIN_TURNS", "6"))
EPISODIC_MIN_SCORE = float(os.getenv("EPISODIC_MIN_SCORE", "0.3"))
EPISODIC_ENABLED = os.getenv("EPISODIC_ENABLED", "true").lower() != "false"

# 语义记忆 (用户画像/偏好)
SEMANTIC_ENABLED = os.getenv("SEMANTIC_ENABLED", "true").lower() != "false"

# JWT
JWT_SECRET = os.getenv("JWT_SECRET", "personal-agent-secret-key-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "1440"))

# Bailian (百炼) — 向量化 & 多模态 & 文档摘要 & Rerank
BAILIAN_API_KEY = os.getenv("BAILIAN_API_KEY", "")
BAILIAN_BASE_URL = os.getenv("BAILIAN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
SUMMARY_MODEL = os.getenv("SUMMARY_MODEL", "deepseek-v4-flash")
MULTIMODAL_MODEL = os.getenv("MULTIMODAL_MODEL", "qwen3.6-flash")
SUMMARY_MAX_CHARS = int(os.getenv("SUMMARY_MAX_CHARS", "15000"))
RERANK_MODEL = os.getenv("RERANK_MODEL", "qwen3-rerank")

# DeepSeek — 对话 LLM
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
CHAT_MODEL = os.getenv("CHAT_MODEL", "deepseek-v4-flash")

# Embedding
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-v4")
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "350"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "60"))

# ChromaDB
CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", str(BASE_DIR / "data" / "chroma"))
CHROMA_COLLECTION = os.getenv("CHROMA_COLLECTION", "knowledge_base")

# RAG 检索配置
RAG_TOP_K = int(os.getenv("RAG_TOP_K", "10"))
DENSE_RECALL_K = int(os.getenv("DENSE_RECALL_K", "20"))
SPARSE_RECALL_K = int(os.getenv("SPARSE_RECALL_K", "20"))
RERANK_TOP_K = int(os.getenv("RERANK_TOP_K", "5"))
RRF_K = int(os.getenv("RRF_K", "60"))
BM25_INDEX_PATH = os.getenv("BM25_INDEX_PATH", str(BASE_DIR / "data" / "bm25_index.json"))

# RAG 可插拔组件开关 (设为 "false" 即可关闭该组件进行 A/B 对比)
RAG_REWRITER_ENABLED = os.getenv("RAG_REWRITER_ENABLED", "true").lower() != "false"
RAG_DENSE_ENABLED = os.getenv("RAG_DENSE_ENABLED", "true").lower() != "false"
RAG_SPARSE_ENABLED = os.getenv("RAG_SPARSE_ENABLED", "true").lower() != "false"
RAG_FUSION_ENABLED = os.getenv("RAG_FUSION_ENABLED", "true").lower() != "false"
RAG_RERANKER_ENABLED = os.getenv("RAG_RERANKER_ENABLED", "true").lower() != "false"

# Neo4j 知识图谱
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")
GRAPH_EXTRACT_MODEL = os.getenv("GRAPH_EXTRACT_MODEL", "deepseek-v4-flash")

# MCP (Model Context Protocol) 外部工具服务器
BAIDU_MAP_API_KEY = os.getenv("BAIDU_MAP_API_KEY", "")
# MCP linkup网络搜索服务
LINKUP_SEARCH_API_KEY = os.getenv("LINKUP_SEARCH_API_KEY", "")

# 意图识别
INTENT_MODEL = os.getenv("INTENT_MODEL", "tongyi-intent-detect-v3")

# 新闻简报定时任务
NEWS_CRON_HOUR = int(os.getenv("NEWS_CRON_HOUR", "8"))
NEWS_CRON_MINUTE = int(os.getenv("NEWS_CRON_MINUTE", "0"))

# 文件上传
UPLOAD_DIR = os.getenv("UPLOAD_DIR", str(BASE_DIR / "data" / "uploads"))
MAX_UPLOAD_SIZE = int(os.getenv("MAX_UPLOAD_SIZE", str(50 * 1024 * 1024)))  # 50MB
