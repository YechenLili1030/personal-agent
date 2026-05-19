# PersonalAgent

个人智能助手系统 — FastAPI + LangChain + Vue 3，集成 RAG 混合检索、三层记忆架构、知识图谱、工具调用、流式对话。

## 核心能力

### 对话
- **WebSocket 流式对话**，LLM 逐 token 输出，支持工具调用中断和恢复
- **ReAct 工具调用**：内置时间查询、天气查询 + MCP 外部工具动态接入，LLM 自主决策，最多 5 轮
- **System Prompt 分层组装**：语义记忆(用户画像) → 情景记忆(历史片段) → 工作记忆(当前会话) → RAG 检索 → 知识图谱 → 当前问题，全部打包为一条 system message

### 三层记忆

| 层 | 存储 | 说明 |
|---|------|------|
| **工作记忆** | Redis 热缓存 → MySQL 降级 | 8K token 滑动窗口管理当前会话上下文 |
| **情景记忆** | ChromaDB `episodic_memory` 集合 | 每 2 轮用 LLM 按 GAOR(目标-行动-结果-反思) 压缩历史片段，检索 top-3 注入上下文 |
| **语义记忆** | MySQL `users.preferences` JSON | 从对话中增量提取用户身份、技能、偏好，Upsert 到画像，让 Agent 持续"认识用户" |

### RAG 检索流水线（可插拔）

```
查询改写 → [稠密检索 + 稀疏检索] → RRF 融合 → Rerank 重排序
   ↓            ↓              ↓           ↓           ↓
 DeepSeek   ChromaDB余弦    BM25关键词   RRF 60     qwen3-rerank
            召回 top-20     召回 top-20   取 top-10    精选 top-5
```

每个组件通过 `.env` 开关独立控制（`RAG_REWRITER_ENABLED` / `RAG_DENSE_ENABLED` / `RAG_SPARSE_ENABLED` / `RAG_FUSION_ENABLED` / `RAG_RERANKER_ENABLED`），关闭任意组件即可 A/B 对比。

- **查询改写**：DeepSeek 将代词指代结合历史补全为独立查询
- **稠密检索**：百炼 `text-embedding-v4` 向量 → ChromaDB 余弦相似度
- **稀疏检索**：BM25 关键词匹配（jieba 分词）
- **RRF 融合**：Reciprocal Rank Fusion 合并双路结果
- **Rerank**：百炼 `qwen3-rerank` 对候选块重新语义打分

### 知识图谱
- 文档向量化后可选构建：LLM 抽取实体和关系 → 写入 Neo4j
- 检索时从召回块中提取实体 → Cypher 查询 1-hop 子图 → 格式化注入上下文
- 删除文档时自动清理关联图谱

### 知识库
- 支持 PDF（含扫描件 OCR）、Word（含文本框）、Excel、Markdown、TXT、图片
- 按文档类型分块：Markdown 按标题 / Excel 按行保留表头 / 通用语义分块
- SHA256 去重 + 可选审查模式（分块后暂停，前端合并或删除分块后继续向量化）
- 文档自动摘要，注入每个 chunk 元数据

### 意图识别
- 百炼 `tongyi-intent-detect-v3` 专用模型判断问题是否需要检索知识库
- `rag`：涉及个人数据的知识检索 / `chat`：通用问答、闲聊、实时查询

## 技术栈

| 层 | 技术 |
|---|---|
| 后端框架 | FastAPI (WebSocket + REST) |
| Agent 框架 | LangChain (ChatOpenAI + @tool) |
| 对话 LLM | DeepSeek `deepseek-v4-flash` |
| 向量化 | 百炼 `text-embedding-v4` |
| 多模态 OCR | 百炼 `qwen3.6-flash` |
| 文档摘要 / 实体抽取 | DeepSeek `deepseek-v4-flash` |
| 意图识别 | 百炼 `tongyi-intent-detect-v3` |
| Rerank | 百炼 `qwen3-rerank` |
| 稠密检索 | ChromaDB（余弦距离） |
| 稀疏检索 | BM25（jieba 分词 + JSON 持久化） |
| 知识图谱 | Neo4j (bolt 直连) |
| 工作记忆缓存 | Redis |
| 关系数据库 | MySQL 8.0 (aiomysql) |
| 前端 | Vue 3 (Composition API) + Vite |

## 项目结构

```
personal-agent/
├── backend/
│   ├── main.py                         # uvicorn 启动入口
│   └── app/
│       ├── main.py                     # FastAPI 应用定义 + lifespan
│       ├── api/                        # 路由层（不含业务逻辑）
│       │   ├── auth.py                 # POST /api/auth/login
│       │   ├── chat.py                 # 会话 REST + WebSocket
│       │   ├── knowledge.py            # 文档上传/列表/图谱/审查
│       │   └── deps.py                 # 权限依赖
│       ├── core/                       # 配置中心
│       │   ├── config.py               # 所有环境变量 + 常量
│       │   ├── database.py             # 异步/同步引擎 + session
│       │   ├── prompts.py              # 所有 LLM 提示词集中管理（10 个）
│       │   └── logging_config.py       # 日志配置
│       ├── models/                     # SQLAlchemy ORM
│       │   ├── user.py                 # User
│       │   ├── chat.py                 # Session / Message
│       │   └── knowledge.py            # KnowledgeDoc / DocChunk
│       ├── schemas/                    # Pydantic 请求/响应模型
│       ├── services/                   # 核心业务逻辑
│       │   ├── chat_service.py         # 对话编排 + build_context + 流式 ReAct
│       │   ├── knowledge_service.py    # 文档解析→摘要→分块→向量化
│       │   ├── vector_store.py         # ChromaDB 封装
│       │   ├── bm25_store.py           # BM25 稀疏检索引擎
│       │   ├── graph_service.py        # Neo4j 图谱构建/查询/删除
│       │   ├── graph_retrieval.py      # 检索阶段实体提取 + 图谱查询
│       │   ├── embedding.py            # 百炼 embedding 调用
│       │   ├── file_parser.py          # PDF/Word/Excel/图片/文本解析
│       │   ├── intent.py               # 百炼意图识别
│       │   └── auth.py                 # JWT 签发与验证
│       ├── rag/                        # RAG 可插拔检索流水线
│       │   ├── base.py                 # SearchResult + 组件接口协议
│       │   ├── pipeline.py             # 流水线编排 + 工厂函数
│       │   ├── query_rewriter.py       # DeepSeek 查询改写
│       │   ├── dense_retriever.py      # ChromaDB 稠密检索
│       │   ├── sparse_retriever.py     # BM25 稀疏检索
│       │   ├── rrf_fusion.py           # RRF 融合
│       │   └── reranker.py             # qwen3-rerank 重排序
│       ├── memory/                     # 三层记忆系统
│       │   ├── working.py              # 工作记忆（Redis + MySQL）
│       │   ├── episodic.py             # 情景记忆（ChromaDB + LLM 压缩）
│       │   └── semantic.py             # 语义记忆（MySQL JSON 画像）
│       ├── mcp/                        # MCP 外部工具客户端
│       │   └── client.py               # 多 MCP Server 连接管理
│       └── tools/                      # LangChain Tool
│           ├── __init__.py             # ALL_TOOLS 注册 + 刷新
│           ├── datetime_tool.py        # 当前时间查询
│           └── weather.py              # 天气查询
├── frontend/
│   └── src/
│       ├── main.js                     # Vue 应用入口
│       ├── App.vue                     # 根组件
│       ├── api/index.js                # Axios 封装
│       ├── router/index.js             # Vue Router
│       ├── views/
│       │   ├── Login.vue               # 登录页
│       │   ├── MainLayout.vue          # 侧边栏 + 路由出口
│       │   ├── Chat.vue                # 对话页 (WebSocket 流式)
│       │   └── Knowledge.vue           # 知识库管理
│       └── components/
│           ├── ConfirmModal.vue        # 通用确认对话框
│           └── ChunkInspectorModal.vue # 分块审查与合并
├── data/                               # 运行时数据
│   ├── chroma/                         # ChromaDB 持久化
│   ├── uploads/                        # 上传文件存储
│   └── bm25_index.json                 # BM25 索引
├── sql/
│   └── init.sql                        # 建表脚本
├── .env.example
└── requirements.txt
```

## 快速开始

### 环境要求

- Python 3.11+
- Node.js 20+
- MySQL 8.0
- Redis（工作记忆缓存，不可用时自动降级 MySQL）
- Neo4j Community Edition（可选，知识图谱功能需要）

### 安装

```bash
git clone https://github.com/你的用户名/personal-agent.git
cd personal-agent

python -m venv .venv
# Windows: .venv\Scripts\activate
# Mac/Linux: source .venv/bin/activate

pip install -r backend/requirements.txt
cd frontend && npm install && cd ..
```

### 配置

```bash
cp .env.example .env
```

编辑 `.env`，填入必要配置：

```ini
# 数据库
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_password
DB_NAME=personal_agent

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379

# JWT
JWT_SECRET=your-secret-key

# DeepSeek API（对话 + 摘要 + 实体抽取 + 查询改写）
DEEPSEEK_API_KEY=sk-xxx
CHAT_MODEL=deepseek-v4-flash

# 百炼 API（向量化 + 多模态 + 意图识别 + Rerank）
BAILIAN_API_KEY=sk-xxx
EMBEDDING_MODEL=text-embedding-v4
MULTIMODAL_MODEL=qwen3.6-flash
INTENT_MODEL=tongyi-intent-detect-v3
RERANK_MODEL=qwen3-rerank

# Neo4j（可选）
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password
```

### 初始化

```bash
mysql -u root -p < sql/init.sql
```

### 启动

```bash
# 终端 1：后端
cd backend && python main.py --port 8000

# 终端 2：前端
cd frontend && npm run dev
```

| 服务 | 地址 |
|---|---|
| 后端 API | http://localhost:8000 |
| Swagger 文档 | http://localhost:8000/docs |
| 前端 | http://localhost:5173 |

默认账号：`admin` / `admin123`

## 使用指南

### 知识库上传

1. 打开知识库页面，拖拽或点击上传文件
2. 支持格式：PDF（含扫描件）、Word、Excel、Markdown、TXT、图片
3. 勾选「上传后检查分块」可暂停在审查状态，手动合并或删除分块
4. 文档处理完成后，点击「构建图谱」抽取知识图谱

### 对话

1. 创建新会话，选择 normal 或 RAG 模式
2. RAG 模式下自动执行检索流水线 + 图谱查询，结果注入上下文
3. 支持工具调用：询问天气、时间等，LLM 自主决定调用

### 知识图谱

- 文档处理完成后可构建图谱：LLM 抽取实体/关系 → 写入 Neo4j
- 检索时自动从召回块中提取实体 → 1-hop 子图查询 → 注入上下文
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
| GET | `/api/knowledge/list` | 文档列表（分页 + 类型/状态筛选） |
| GET | `/api/knowledge/{doc_id}` | 文档详情 |
| DELETE | `/api/knowledge/{doc_id}` | 删除文档及关联图谱 |
| GET | `/api/knowledge/{doc_id}/chunks` | 获取文档分块列表 |
| PUT | `/api/knowledge/chunks/merge` | 合并相邻分块 |
| DELETE | `/api/knowledge/chunks/{chunk_id}` | 删除单个分块 |
| POST | `/api/knowledge/{doc_id}/finalize` | 审查完成后触发向量化 |
| POST | `/api/knowledge/{doc_id}/build-graph` | 构建知识图谱 |
| GET | `/api/knowledge/{doc_id}/graph` | 获取图谱数据（前端可视化） |
| DELETE | `/api/knowledge/{doc_id}/graph` | 删除知识图谱 |

### 对话

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/chat/session/create` | 创建会话 |
| GET | `/api/chat/session/list` | 会话列表 |
| PUT | `/api/chat/session/{id}` | 更新会话（标题/模式/状态） |
| DELETE | `/api/chat/session/{id}` | 删除会话及消息 |
| GET | `/api/chat/message/{id}/history` | 消息历史 |
| WS | `/api/chat/ws/{session_id}?token=` | WebSocket 流式对话 |

## 环境变量完整列表

### 数据库

| 变量 | 默认值 | 说明 |
|---|---|---|
| `DB_HOST` | localhost | MySQL 地址 |
| `DB_PORT` | 3306 | MySQL 端口 |
| `DB_USER` | root | MySQL 用户名 |
| `DB_PASSWORD` | — | MySQL 密码 |
| `DB_NAME` | personal_agent | 数据库名 |

### Redis

| 变量 | 默认值 | 说明 |
|---|---|---|
| `REDIS_HOST` | localhost | Redis 地址 |
| `REDIS_PORT` | 6379 | Redis 端口 |
| `WORKING_MEMORY_MAX_TOKENS` | 8000 | 工作记忆 token 窗口 |
| `WORKING_MEMORY_REDIS_TTL` | 1800 | Redis 缓存过期时间(秒) |

### LLM

| 变量 | 默认值 | 说明 |
|---|---|---|
| `DEEPSEEK_API_KEY` | — | DeepSeek API Key |
| `DEEPSEEK_BASE_URL` | https://api.deepseek.com | DeepSeek 地址 |
| `CHAT_MODEL` | deepseek-v4-flash | 对话模型 |
| `SUMMARY_MODEL` | deepseek-v4-flash | 文档摘要模型 |
| `GRAPH_EXTRACT_MODEL` | deepseek-v4-flash | 图谱实体抽取模型 |
| `BAILIAN_API_KEY` | — | 百炼 API Key |
| `BAILIAN_BASE_URL` | https://dashscope.aliyuncs.com/compatible-mode/v1 | 百炼地址 |
| `EMBEDDING_MODEL` | text-embedding-v4 | 向量化模型 |
| `MULTIMODAL_MODEL` | qwen3.6-flash | 多模态 OCR 模型 |
| `INTENT_MODEL` | tongyi-intent-detect-v3 | 意图识别模型 |
| `RERANK_MODEL` | qwen3-rerank | Rerank 重排序模型 |

### RAG 检索

| 变量 | 默认值 | 说明 |
|---|---|---|
| `RAG_REWRITER_ENABLED` | true | 查询改写开关 |
| `RAG_DENSE_ENABLED` | true | 稠密检索开关 |
| `RAG_SPARSE_ENABLED` | true | 稀疏检索开关 |
| `RAG_FUSION_ENABLED` | true | RRF 融合开关 |
| `RAG_RERANKER_ENABLED` | true | Rerank 开关 |
| `DENSE_RECALL_K` | 20 | 稠密检索召回数 |
| `SPARSE_RECALL_K` | 20 | 稀疏检索召回数 |
| `RAG_TOP_K` | 10 | RRF 融合后保留数 |
| `RERANK_TOP_K` | 5 | Rerank 精选数 |
| `RRF_K` | 60 | RRF 平滑参数 |

### 记忆

| 变量 | 默认值 | 说明 |
|---|---|---|
| `EPISODIC_ENABLED` | true | 情景记忆开关 |
| `SEMANTIC_ENABLED` | true | 语义记忆开关 |
| `EPISODIC_TOP_K` | 3 | 情景记忆检索条数 |
| `EPISODIC_MIN_TURNS` | 6 | 最少消息数才触发压缩 |
| `EPISODIC_MIN_SCORE` | 0.3 | 情景记忆最低相似度 |

### 分块

| 变量 | 默认值 | 说明 |
|---|---|---|
| `CHUNK_SIZE` | 350 | 文本分块大小 |
| `CHUNK_OVERLAP` | 60 | 分块重叠量 |

### 其他

| 变量 | 默认值 | 说明 |
|---|---|---|
| `JWT_SECRET` | — | JWT 签名密钥 |
| `JWT_EXPIRE_MINUTES` | 1440 | JWT 过期时间(分钟) |
| `NEO4J_URI` | bolt://localhost:7687 | Neo4j 地址 |
| `NEO4J_USER` | neo4j | Neo4j 用户名 |
| `NEO4J_PASSWORD` | — | Neo4j 密码 |
| `CHROMA_PERSIST_DIR` | data/chroma | ChromaDB 持久化目录 |
| `UPLOAD_DIR` | data/uploads | 上传文件目录 |
| `MAX_UPLOAD_SIZE` | 52428800 | 上传文件大小上限(字节) |
