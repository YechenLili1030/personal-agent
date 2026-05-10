# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

PersonalAgent — 个人智能助手系统。FastAPI 后端 + Vue 3 前端，集成 RAG 知识库、工具调用、流式对话。

## 启动命令

```bash
# 后端 (需要先启动 MySQL，执行 sql/init.sql 建库建表)
cd backend && ../.venv/Scripts/uvicorn app.main:app --reload --port 8000

# 前端
cd frontend && npm run dev
```

- 后端: `http://localhost:8000` (Swagger: `/docs`)
- 前端: `http://localhost:5173` (Vite 代理 `/api` 到后端，含 WebSocket)
- 数据库: MySQL `localhost:3306` / `personal_agent`

## LLM 服务分布

系统使用三个不同的模型提供商，通过 `langchain_openai.ChatOpenAI` 统一封装（均为 OpenAI 兼容 API）:

| 用途 | Provider | 模型 | 配置位置 |
|------|----------|------|----------|
| 对话 + 工具调用 | DeepSeek | `deepseek-v4-flash` | `chat_service._build_llm()` |
| 文档摘要 + 多模态 | 百炼 Bailian | `qwen-long-latest` / `qwen3.6-flash` | `knowledge_service._build_llm()` |
| 向量化 | 百炼 Bailian | `text-embedding-v4` | `embedding.py` (原生 OpenAI client) |

`.env` 中 `DEEPSEEK_API_KEY` 和 `BAILIAN_API_KEY` 分别配置两套凭证。

## 架构要点

```
backend/app/
├── api/          # FastAPI 路由层，不含业务逻辑
│   ├── auth.py       # POST /api/auth/login
│   ├── chat.py       # 会话/消息 CRUD + WebSocket /api/chat/ws/{id}
│   ├── knowledge.py  # 知识库上传/列表/删除
│   └── deps.py       # require_user 共享依赖 (JWT 解析)
├── services/     # 核心业务逻辑
│   ├── chat_service.py    # 对话: 上下文构建、流式 LLM、工具 ReAct 循环
│   ├── knowledge_service.py  # 文档流水线: 解析→摘要→分块→向量化
│   ├── file_parser.py    # 多格式解析 (PDF/Word/Excel/MD/图片)
│   ├── embedding.py      # 百炼 text-embedding-v4 向量化
│   └── vector_store.py   # ChromaDB 封装
├── models/       # SQLAlchemy ORM (无 FK 约束，仅逻辑关联)
├── tools/        # LangChain @tool (weather, datetime)
├── core/
│   ├── config.py     # 所有配置项 (env → Python)
│   ├── prompts.py    # 所有 LLM 提示词统一管理
│   └── logging_config.py
└── main.py       # FastAPI 应用入口 + lifespan + 请求日志中间件
```

### 对话流程 (WebSocket)

1. 客户端连接 `ws://host/api/chat/ws/{session_id}?token=xxx`
2. 发送 `{"type":"chat", "content":"...", "mode":"rag"}`
3. 服务端: 保存用户消息 → `build_context()` (RAG 模式走 ChromaDB 向量检索 + 文档摘要分组) → `run_chat_agent()` 流式 LLM + 工具调用
4. 逐 token 推送 `{"type":"token","data":"..."}`，完成推 `{"type":"done"}`

### 知识库流水线

上传 → 解析文件 (`file_parser.parse_file` 返回 `ParseResult`，含 `structure` 属性) → LLM 摘要 (百炼) → 按类型分块:
- `semantic`: `RecursiveCharacterTextSplitter` (PDF/Word/TXT/图片)
- `excel`: 按 Sheet 分组，每约20行+表头为一个 chunk
- `markdown`: `MarkdownHeaderTextSplitter` 按标题切分

→ SHA256 hash 去重 (MySQL `doc_chunks.content_hash` UNIQUE) → 向量化 → ChromaDB

扫描件 PDF (<100 字文本) 和图片自动走百炼 `qwen3.6-flash` 多模态提取。

### 工具调用 (ReAct)

`chat_service.run_chat_agent()` 使用 `llm.bind_tools(ALL_TOOLS)` + 手动流式循环:
- 解析 `tool_call_chunks` 累积工具调用
- 执行工具后将结果以 `"工具返回结果:\n..."` 注入消息列表
- 最多 5 轮迭代

新增工具: 在 `tools/` 下创建 `@tool` 装饰函数，加入 `tools/__init__.py` 的 `ALL_TOOLS` 列表。

### 数据库

不使用外键约束 (DeepSeek API thinking 模式有兼容问题)。全部用 INDEX 做逻辑关联。建表 SQL 在 `sql/init.sql`。

### 前端

Vue 3 + JS + Vue Router。三个页面: Login → Chat → Knowledge。`ConfirmModal` 组件替代原生 `confirm()`。CSS 变量定义在 `App.vue` (`--ink-black`, `--paper`, `--vermillion` 等，文人书斋风格)。

## 重要约束

- 不要在 `ChatOpenAI` 上使用 `model_kwargs={"thinking": ...}` — 会作为 API 参数而非 body 传递导致 `TypeError`
- 不要用 `langchain.agents.create_agent` — DeepSeek 的 `reasoning_content` 回传与 LangGraph agent 内部消息处理不兼容
- 多模态调用使用原生 OpenAI client 的 `HumanMessage(content=[...])` 传递 image_url
- `Message` ORM 的 metadata 字段在 Python 侧名为 `msg_metadata` (避免与 SQLAlchemy 保留字冲突)，DB 列名为 `metadata`
