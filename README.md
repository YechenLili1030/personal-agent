# PersonalAgent

个人智能助手系统 —— 基于 FastAPI + LangChain + Vue 3，支持 RAG 混合检索、知识图谱、工具调用。

## 核心能力

### 检索增强生成 (RAG)
- **混合检索**：稠密向量检索 (ChromaDB) + 稀疏关键词检索 (BM25)，双路各召回 20 条，RRF 融合排序
- **知识图谱检索**：从召回结果中提取实体 → 查询 Neo4j 1-hop 子图 → 合并上下文
- **分块策略**：Markdown 按标题 / Excel 按行 / 通用语义分块，自动去重
- **文档处理**：PDF（含扫描件 OCR）、Word、Excel、图片、TXT、Markdown
- **用户隔离**：所有检索路径均按 user_id 过滤

### 对话
- **WebSocket 流式对话**，支持 normal / RAG 双模式实时切换
- **工具调用 (ReAct)**：内置时间查询、天气查询等 Tool，LLM 自主决定调用
- **上下文窗口**：最近 20 条会话历史注入系统提示词

### 知识库管理
- 前端支持文档上传、状态筛选、分块审查与合并
- 可选构建知识图谱（百炼 qwen-plus 抽取实体/关系 → Neo4j）
- 文档自动摘要，注入每个 chunk 元数据

## 技术栈

| 层 | 技术 |
|---|---|
| 后端框架 | FastAPI |
| Agent 框架 | LangChain (ChatOpenAI + tools) |
| 对话 LLM | DeepSeek (deepseek-v4-flash) |
| 向量化 | 百炼 text-embedding-v4 |
| 文档摘要 / 实体抽取 | 百炼 qwen-long / qwen-plus |
| 多模态 OCR | 百炼 qwen3.6-flash |
| 稠密检索 | ChromaDB (L2 距离) |
| 稀疏检索 | BM25 (jieba 分词 + 纯 Python 内存索引) |
| 知识图谱 | Neo4j (bolt 直连) |
| 关系数据库 | MySQL 8.0 (aiomysql) |
| 前端 | Vue 3 (Composition API) + Vite |

## 检索流水线

```
用户问题
    ├→ 稠密检索 (ChromaDB, 20条, 按user_id过滤)
    └→ 稀疏检索 (BM25, 20条, 按user_id过滤)
         ↓
    RRF 融合 → Top-20 chunks
         ↓
    ┌────┴────┐
    │ 按文档分组 → rag_section
    │
    │ 从 chunks 提取实体 (jieba 词性标注 + qwen-plus 兜底)
    │ → Cypher 查询 Neo4j 1-hop 子图
    │ → graph_section
    │
    └────┬────┘
         ↓
    system prompt = 历史对话 + 参考资料 + 知识图谱 + 用户问题
```

## 项目结构

```
personal-agent/
├── backend/
│   ├── main.py                       # uvicorn 启动入口
│   └── app/
│       ├── main.py                   # FastAPI 应用定义 + lifespan
│       ├── api/                      # 路由层
│       │   ├── auth.py               # POST /api/auth/login
│       │   ├── chat.py               # 会话 REST + WebSocket
│       │   ├── knowledge.py          # 文档上传 / 列表 / 图谱构建 / 审查
│       │   └── deps.py               # 权限依赖
│       ├── core/                     # 配置中心
│       │   ├── config.py             # 所有环境变量 + 常量
│       │   ├── database.py           # 异步 / 同步引擎 + session
│       │   ├── prompts.py            # LLM 提示词集中管理
│       │   └── logging_config.py     # 日志配置
│       ├── models/                   # SQLAlchemy ORM
│       │   ├── user.py               # User
│       │   ├── chat.py               # Session / Message
│       │   └── knowledge.py          # KnowledgeDoc / DocChunk
│       ├── schemas/                  # Pydantic 请求 / 响应模型
│       │   ├── user.py
│       │   ├── chat.py
│       │   └── knowledge.py
│       ├── services/                 # 核心业务逻辑
│       │   ├── chat_service.py       # 对话编排 + build_context + RRF 融合
│       │   ├── knowledge_service.py  # 文档解析 → 摘要 → 分块 → 向量化
│       │   ├── vector_store.py       # ChromaDB 封装 (单例管理)
│       │   ├── bm25_store.py         # BM25 稀疏检索引擎 (内存索引 + JSON 持久化)
│       │   ├── graph_service.py      # Neo4j 图谱构建 / 查询 / 删除
│       │   ├── graph_retrieval.py    # 检索阶段实体提取 + 图谱查询 (混合策略)
│       │   ├── embedding.py          # 百炼 text-embedding-v4
│       │   ├── file_parser.py        # PDF/Word/Excel/图片/文本解析
│       │   └── auth.py               # JWT 签发与验证
│       └── tools/                    # LangChain Tool
│           ├── __init__.py           # ALL_TOOLS 注册
│           ├── datetime_tool.py      # 当前时间查询
│           └── weather.py            # 天气查询
├── frontend/
│   └── src/
│       ├── main.js                   # Vue 应用入口
│       ├── App.vue                   # 根组件
│       ├── api/index.js              # Axios 封装 (所有 API 函数)
│       ├── router/index.js           # Vue Router (/login, /chat, /knowledge)
│       ├── views/
│       │   ├── Login.vue             # 登录页
│       │   ├── MainLayout.vue        # 侧边栏 + 路由出口
│       │   ├── Chat.vue              # 对话页 (WebSocket 流式)
│       │   └── Knowledge.vue         # 知识库管理 (上传/列表/图谱/审查)
│       └── components/
│           ├── ConfirmModal.vue      # 通用确认对话框
│           └── ChunkInspectorModal.vue # 分块审查与合并
├── data/                             # 运行时数据 (自动生成)
│   ├── chroma/                       # ChromaDB 持久化文件
│   ├── uploads/                      # 上传文件存储
│   └── bm25_index.json               # BM25 索引文件
├── sql/
│   └── init.sql                      # 建表脚本
├── .env.example                      # 环境变量模板
└── requirements.txt
```

## 快速开始

### 环境要求

- Python 3.11+
- Node.js 20+
- MySQL 8.0
- Neo4j Community Edition (可选，知识图谱功能需要)

### 安装

```bash
git clone https://github.com/你的用户名/personal-agent.git
cd personal-agent

# 创建虚拟环境
python -m venv .venv
# Windows: .venv\Scripts\activate
# Mac/Linux: source .venv/bin/activate

# 安装依赖
pip install -r backend/requirements.txt
cd frontend && npm install && cd ..
```

### 配置

```bash
cp .env.example .env
```

编辑 `.env`，填入 API Key 等必要配置：

```ini
# 数据库
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_password
DB_NAME=personal_agent

# JWT
JWT_SECRET=your-secret-key

# 百炼 API (向量化 / 多模态 / 摘要 / 图谱实体抽取)
BAILIAN_API_KEY=sk-xxx
SUMMARY_MODEL=qwen-long-latest
MULTIMODAL_MODEL=qwen3.6-flash
GRAPH_EXTRACT_MODEL=qwen-plus

# DeepSeek (对话 LLM)
DEEPSEEK_API_KEY=sk-xxx
CHAT_MODEL=deepseek-v4-flash

# Neo4j (知识图谱，可选)
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password

# 检索参数
DENSE_RECALL_K=20
SPARSE_RECALL_K=20
RRF_K=60
```

### 初始化数据库

```bash
mysql -u root -p < sql/init.sql
```

Neo4j (可选)：
1. 安装 [Neo4j Community Edition](https://neo4j.com/download/)
2. 创建本地数据库，设置用户名密码
3. 在 `.env` 中配置连接参数

### 启动

```bash
# 终端 1：后端
cd backend
python main.py

# 终端 2：前端
cd frontend
npm run dev
```

> 服务启动时自动执行数据库迁移（添加 `graph_status` 列）、加载 BM25 索引。
> 首次使用时 BM25 索引为空，上传文档后自动构建。

| 服务 | 地址 |
|---|---|
| 后端 API | http://localhost:8000 |
| API 文档 (Swagger) | http://localhost:8000/docs |
| 前端 | http://localhost:5173 |

默认账号：`admin` / `admin123`

## 使用指南

### 知识库上传

1. 打开知识库页面，拖拽或点击上传文件
2. 勾选「上传后检查分块」可暂停在审查状态，手动合并拆分不当的相邻分块
3. 文档处理完成后（状态变为"已完成"），点击「构建图谱」抽取知识图谱

### RAG 对话

1. 创建新会话，选择 RAG 模式
2. 提问时系统自动执行混合检索 + 图谱查询，结果注入上下文
3. 可在对话中切换 normal / RAG 模式

### 知识图谱

- 文档处理完成后，点击「构建图谱」→ 百炼 qwen-plus 抽取实体/关系 → 写入 Neo4j
- 检索时自动从召回结果中提取实体 → 1-hop 子图查询 → 格式化注入提示词
- 删除文档时自动清理关联图谱

## API 参考

### 认证

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/auth/login` | 登录，返回 JWT token |

### 知识库

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/knowledge/upload` | 上传文档 (multipart/form-data) |
| GET | `/api/knowledge/list` | 文档列表 (分页 + 筛选) |
| GET | `/api/knowledge/{doc_id}` | 文档详情 |
| DELETE | `/api/knowledge/{doc_id}` | 删除文档及关联图谱 |
| GET | `/api/knowledge/{doc_id}/chunks` | 获取文档分块列表 |
| PUT | `/api/knowledge/chunks/merge` | 合并相邻分块 |
| DELETE | `/api/knowledge/chunks/{chunk_id}` | 删除单个分块 |
| POST | `/api/knowledge/{doc_id}/finalize` | 审查完成后触发向量化 |
| POST | `/api/knowledge/{doc_id}/build-graph` | 构建知识图谱 |
| DELETE | `/api/knowledge/{doc_id}/graph` | 删除知识图谱 |

### 对话

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/chat/session/create` | 创建会话 |
| GET | `/api/chat/session/list` | 会话列表 |
| DELETE | `/api/chat/session/{id}` | 删除会话 |
| GET | `/api/chat/message/{id}/history` | 消息历史 |
| WS | `/api/chat/ws/{session_id}?token=` | WebSocket 流式对话 |

## 环境变量完整列表

| 变量 | 默认值 | 说明 |
|---|---|---|
| `DB_HOST` | localhost | MySQL 地址 |
| `DB_PORT` | 3306 | MySQL 端口 |
| `DB_USER` | root | MySQL 用户名 |
| `DB_PASSWORD` | — | MySQL 密码 |
| `DB_NAME` | personal_agent | 数据库名 |
| `JWT_SECRET` | — | JWT 签名密钥 |
| `BAILIAN_API_KEY` | — | 百炼 API Key |
| `DEEPSEEK_API_KEY` | — | DeepSeek API Key |
| `CHAT_MODEL` | deepseek-v4-flash | 对话模型 |
| `SUMMARY_MODEL` | qwen-long-latest | 文档摘要模型 |
| `GRAPH_EXTRACT_MODEL` | qwen-plus | 图谱实体抽取模型 |
| `EMBEDDING_MODEL` | text-embedding-v4 | 向量化模型 |
| `NEO4J_URI` | bolt://localhost:7687 | Neo4j 连接地址 |
| `NEO4J_USER` | neo4j | Neo4j 用户名 |
| `NEO4J_PASSWORD` | — | Neo4j 密码 |
| `DENSE_RECALL_K` | 20 | 稠密检索召回数 |
| `SPARSE_RECALL_K` | 20 | 稀疏检索召回数 |
| `RRF_K` | 60 | RRF 平滑参数 |
| `CHUNK_SIZE` | 350 | 文本分块大小 |
| `CHUNK_OVERLAP` | 40 | 分块重叠量 |
