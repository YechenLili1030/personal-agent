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

# JWT
JWT_SECRET = os.getenv("JWT_SECRET", "personal-agent-secret-key-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "1440"))

# Bailian (百炼) — 向量化 & 多模态 & 文档摘要
BAILIAN_API_KEY = os.getenv("BAILIAN_API_KEY", "")
BAILIAN_BASE_URL = os.getenv("BAILIAN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
SUMMARY_MODEL = os.getenv("SUMMARY_MODEL", "qwen-long-latest")
MULTIMODAL_MODEL = os.getenv("MULTIMODAL_MODEL", "qwen3.6-flash")
SUMMARY_MAX_CHARS = int(os.getenv("SUMMARY_MAX_CHARS", "15000"))

# DeepSeek — 对话 LLM
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
CHAT_MODEL = os.getenv("CHAT_MODEL", "deepseek-v4-flash")

# Embedding
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-v4")
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "350"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "40"))

# ChromaDB
CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", str(BASE_DIR / "data" / "chroma"))
CHROMA_COLLECTION = os.getenv("CHROMA_COLLECTION", "knowledge_base")

# BM25 稀疏检索
DENSE_RECALL_K = int(os.getenv("DENSE_RECALL_K", "20"))
SPARSE_RECALL_K = int(os.getenv("SPARSE_RECALL_K", "20"))
RRF_K = int(os.getenv("RRF_K", "60"))
BM25_INDEX_PATH = os.getenv("BM25_INDEX_PATH", str(BASE_DIR / "data" / "bm25_index.json"))

# Neo4j 知识图谱
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")
GRAPH_EXTRACT_MODEL = os.getenv("GRAPH_EXTRACT_MODEL", "qwen-plus")

# MCP (Model Context Protocol) 外部工具服务器
BAIDU_MAP_API_KEY = os.getenv("BAIDU_MAP_API_KEY", "")

# 文件上传
UPLOAD_DIR = os.getenv("UPLOAD_DIR", str(BASE_DIR / "data" / "uploads"))
MAX_UPLOAD_SIZE = int(os.getenv("MAX_UPLOAD_SIZE", str(50 * 1024 * 1024)))  # 50MB
