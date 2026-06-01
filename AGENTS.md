# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## 项目概述

PersonalAgent — 个人智能助手系统。FastAPI 后端 + Vue 3 前端，集成 RAG 知识库、四层记忆架构、工具调用、流式对话。

## 启动命令

```bash
# 后端 (需要先启动 MySQL 和 Redis)
cd backend && ../.venv/Scripts/python main.py --port 8000

# 前端
cd frontend && npm run dev
```

- 后端: `http://localhost:8000` (Swagger: `/docs`)
- 前端: `http://localhost:5173` (Vite 代理 `/api` 到后端，含 WebSocket)
- MySQL: `localhost:3306` / `personal_agent`, 建表 SQL 在 `sql/`
- Redis: `localhost:6379` (工作记忆热缓存，不可用时自动降级 MySQL)

## LLM 服务分布

| 用途 | Provider | 模型 | 调用方式 |
|------|----------|------|----------|
| 对话 + 工具调用 | DeepSeek | `deepseek-v4-flash` | `ChatOpenAI` (langchain) |
| 文档摘要 | DeepSeek | `deepseek-v4-flash` | `ChatOpenAI` (langchain) |
| 实体/关系抽取 | DeepSeek | `deepseek-v4-flash` | `OpenAI` client (原生) |
| 多模态解析 | 百炼 Bailian | `qwen3.6-flash` | `ChatOpenAI` (langchain) |
| 向量化 | 百炼 Bailian | `text-embedding-v4` | `OpenAI` client (原生) |
| Rerank | 百炼 Bailian | `qwen3-rerank` | `OpenAI` client (原生) |
| 意图识别 | 百炼 Bailian | `tongyi-intent-detect-v3` | `OpenAI` client (原生) |

`.env` 中 `DEEPSEEK_API_KEY` 和 `BAILIAN_API_KEY` 分别配置两套凭证。

## 架构要点

```
backend/app/
├── api/            # FastAPI 路由层，不含业务逻辑
├── services/       # 核心业务逻辑 (chat, knowledge, graph 等)
├── rag/            # RAG 可插拔检索流水线 (见下方)
├── memory/         # 四层记忆系统 (见下方)
├── mcp/            # MCP 外部工具客户端
├── models/         # SQLAlchemy ORM (无 FK 约束)
├── tools/          # LangChain @tool (weather, datetime, MCP 动态加载)
├── core/           # config.py + prompts.py + database.py
└── main.py         # FastAPI 应用入口 + lifespan
```

### 对话流程 (WebSocket)

1. 客户端连接 `ws://host/api/chat/ws/{session_id}?token=xxx`
2. 发送 `{"type":"chat", "content":"..."}`
3. 服务端: 保存消息 → `build_context()` 构建 system prompt → `run_chat_agent()` 流式 LLM
4. build_context 组装顺序: **语义记忆(用户画像) → 情景记忆(历史片段) → 工作记忆(当前会话) → RAG 检索 → 知识图谱 → 当前问题**
5. 上下文全部打包到一条 system message，只发一条 user message

### RAG 检索流水线 (`backend/app/rag/`)

可插拔模块，每个组件通过 `.env` 开关独立控制 (true/false):

```
查询改写 (deepseek) → [稠密检索 (ChromaDB) + 稀疏检索 (BM25)] → RRF 融合 → Rerank (qwen3-rerank)
```

| 模块 | 文件 | 开关 |
|------|------|------|
| 查询改写 | `rag/query_rewriter.py` | `RAG_REWRITER_ENABLED` |
| 稠密检索 | `rag/dense_retriever.py` | `RAG_DENSE_ENABLED` |
| 稀疏检索 | `rag/sparse_retriever.py` | `RAG_SPARSE_ENABLED` |
| RRF 融合 | `rag/rrf_fusion.py` | `RAG_FUSION_ENABLED` |
| Rerank | `rag/reranker.py` | `RAG_RERANKER_ENABLED` |

统一接口定义在 `rag/base.py` (Protocol 类): `QueryRewriter`, `Retriever`, `Fusion`, `Reranker`。
默认流水线由 `rag/pipeline.py` 的 `get_pipeline()` 从环境变量构建。
`chat_service.build_context()` 已简化为 `pipeline.run(query, history, user_id)` 单行调用。

### 四层记忆系统 (`backend/app/memory/`)

| 层 | 文件 | 存储 | 时机 |
|---|------|------|------|
| 工作记忆 | `memory/working.py` | Redis 热缓存 → MySQL 降级 | 每轮实时, 8K token 滑动窗口 |
| 情景记忆 | `memory/episodic.py` | ChromaDB `episodic_memory` 集合 | 每 2 轮压缩一次, 检索 top-3 |
| 语义记忆 | `memory/semantic.py` | MySQL `users.preferences` JSON | 每 2 轮提取一次, Upsert |
| 程序记忆 | `core/prompts.py` | 文件系统 (Git) | 每轮底层加载 |

情景记忆与知识库使用独立 ChromaDB 集合 (`episodic_memory` vs `knowledge_base`), 互不干扰。
记忆系统通过 `.env` 开关控制: `EPISODIC_ENABLED`, `SEMANTIC_ENABLED`。

### 知识库流水线

上传 → 解析 → LLM 摘要 (DeepSeek) → 按类型分块 → SHA256 去重 → 可选审查 (`inspect` 模式暂停) → 向量化 (余弦相似度) → ChromaDB + BM25 索引

文档分块审查: 上传时勾选"审查分块"，分块后暂停并在前端显示所有分块。用户可将相邻块的指定文本合并或删除分块，确认后继续向量化。

### 工具调用 (ReAct)

`run_chat_agent()` 使用 `llm.bind_tools(ALL_TOOLS)` + 手动流式循环, 最多 5 轮。
`ALL_TOOLS` = 本地工具 (weather, datetime) + MCP 动态加载工具。
`tools/refresh_all_tools()` 在启动时调用，之后每次 `run_chat_agent` 用 `tool_map = {t.name: t for t in ALL_TOOLS}` 实时构建查找表。
MCP 工具只支持异步调用，使用 `await fn.ainvoke(args)`。
工具执行异常时错误信息注入到消息列表，供 LLM 调整策略。

## 重要约束

- 不要在 `ChatOpenAI` 上使用 `model_kwargs={"thinking": ...}` — 会作为 API 参数而非 body 传递导致 `TypeError`。禁用 DeepSeek thinking 使用原生 `OpenAI` client + `extra_body={"thinking": {"type": "disabled"}}`
- 不要用 `langchain.agents.create_agent` — DeepSeek `reasoning_content` 与 LangGraph agent 消息处理不兼容
- `Message` ORM 的 metadata 字段 Python 侧名为 `msg_metadata`，DB 列名为 `metadata`
- 编辑 `prompts.py` 确保使用英文直引号 `"""`，部分编辑器自动转中文弯引号导致语法错误
- 后端入口是 `backend/main.py`，FastAPI 应用在 `backend/app/main.py`
- jieba 0.34 版本: `lcut` 不存在，用 `list(jieba.cut(text))`；`pseg.cut` 返回的 pair 对象不支持元组解包，用 `pair.word` / `pair.flag`
- ChromaDB 集合使用 `metadata={"hnsw:space": "cosine"}` 指定余弦距离，但已有集合不受影响，需删除 `data/chroma/` 重建
- Prompt 模板中的 `{...}` 示例需用 `{{...}}` 转义，否则 `.format()` 报 `IndexError`
