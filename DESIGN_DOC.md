# 个人智能助手 Agent 系统 — 设计文档

---

# 第一部分：需求文档（PRD）

## 1. 项目概述

| 项 | 内容 |
|---|------|
| **项目名称** | PersonalAgent — 个人智能助手 Agent 系统 |
| **目标用户** | 个人用户（开发者/知识工作者），单用户模式 |
| **核心价值** | 将个人知识库（文档、笔记、文件）与 LLM 深度结合，通过 RAG + 知识图谱提供上下文增强的智能问答；同时支持工具调用、Skill 编排、MCP 协议扩展，形成可演进的个人 AI 助理 |

### 核心场景

1. **知识库问答** — 用户上传工作文档，助手基于文档内容回答问题，附带来源引用。
2. **多轮深度对话** — 长上下文对话，助手记住用户偏好和历史，提供个性化回答。
3. **任务执行** — 复杂任务自动拆解为多步计划，逐步执行并反馈进度。
4. **能力扩展** — 通过 MCP 协议接入外部工具（数据库查询、API 调用、文件操作等）。

---

## 2. 功能清单

### 2.1 知识库管理模块

| ID | 功能点 | 优先级 | 验收标准 |
|----|--------|--------|----------|
| KB-01 | 上传文件（PDF/Word/Excel/TXT/Markdown/图片） | P0 | 单文件 ≤50MB 上传成功，返回文档 ID；图片自动 OCR 提取文字 |
| KB-02 | 文件向量化存储（Qwen Embedding + ChromaDB） | P0 | 上传后 30s 内完成分块(chunk_size=500, overlap=50)与向量化，可通过 collection 查询 |
| KB-03 | 知识库列表查询 | P0 | 分页返回文档元数据（文件名、类型、大小、上传时间、处理状态） |
| KB-04 | 删除文档 | P0 | 删除文档记录 + 对应向量数据 + 关联知识图谱节点（级联删除） |
| KB-05 | 知识图谱构建（实体关系抽取 + Neo4j 存储） | P1 | 对文档内容做 NER + RE，实体和关系写入 Neo4j；支持按文档 ID 触发构建 |
| KB-06 | 知识图谱可视化查询 | P2 | 前端以关系图展示实体和关联，支持节点点击查看详情 |
| KB-07 | 知识库分类/标签管理 | P2 | 支持创建分类目录，文档可挂载到分类下 |

### 2.2 对话模块

| ID | 功能点 | 优先级 | 验收标准 |
|----|--------|--------|----------|
| CH-01 | 普通对话模式 | P0 | 仅使用 LLM 自身能力回答，不检索知识库 |
| CH-02 | 知识库增强模式（RAG + 知识图谱） | P0 | 开启后，回答前先检索相关文档片段 + 知识图谱子图，注入 Prompt；回答附带来源引用 |
| CH-03 | WebSocket 流式输出 | P0 | 消息通过 WS 连接发送，模型生成 token 实时推送到前端，延迟感知 < 500ms |
| CH-04 | 多轮对话上下文管理 | P0 | 同一 session 内携带历史消息窗口（最近 N 轮，可配置）；超出窗口部分摘要压缩 |
| CH-05 | 会话创建与管理 | P0 | 创建会话返回 session_id，支持会话列表、重命名、删除 |
| CH-06 | 对话历史存储 | P0 | 所有消息持久化到 MySQL，支持按会话查询完整历史 |
| CH-07 | 长期记忆（用户画像） | P1 | ChromaDB 存储用户偏好/事实；Redis 管理短期上下文（最近 30 轮）；对话时可选择是否启用记忆 |
| CH-08 | 对话模式切换 | P0 | 前端单次对话内可切换"普通模式"和"知识增强模式" |

### 2.3 工具调用模块（暂定，为扩展预留）

| ID | 功能点 | 优先级 | 验收标准 |
|----|--------|--------|----------|
| TL-01 | 工具注册与发现 | P2 | 工具实现统一基类，注册后出现在可用工具列表 |
| TL-02 | LLM 自动选择工具调用 | P2 | Agent 根据用户意图自主选择合适的工具并执行 |

### 2.4 Skill 模块（暂定，为扩展预留）

| ID | 功能点 | 优先级 | 验收标准 |
|----|--------|--------|----------|
| SK-01 | Skill 注册与列表 | P2 | Skill 实现统一基类，注册后可查询 |
| SK-02 | Skill 手动执行 | P2 | 通过 API 触发 Skill 执行并返回结果 |

### 2.5 MCP 集成模块

| ID | 功能点 | 优先级 | 验收标准 |
|----|--------|--------|----------|
| MC-01 | MCP Server 注册 | P1 | 支持 stdio/SSE 两种传输方式注册 MCP Server，验证连接可达 |
| MC-02 | MCP Server 列表与管理 | P1 | 查看已注册 Server 及其提供的工具/资源列表；支持删除 |
| MC-03 | MCP 工具调用 | P1 | LLM 可调用 MCP Server 暴露的工具，携带正确的参数，返回结果 |
| MC-04 | 内置 MCP Server 示例（SQLite 查询） | P2 | 开箱可用，用户问"帮我查数据库"时通过 MCP 执行 SQL 并返回 |

### 2.6 任务规划与执行（LangGraph）

| ID | 功能点 | 优先级 | 验收标准 |
|----|--------|--------|----------|
| LG-01 | Plan 节点 — 任务拆解 | P1 | 接收用户复杂请求，输出步骤列表（每步含：动作类型、参数、预期结果） |
| LG-02 | Execute 节点 — 逐步执行 | P1 | 按计划顺序执行每一步，记录中间结果 |
| LG-03 | Reflect 节点 — 反思/重试 | P1 | 评估执行结果是否符合预期；不符合则重试或重新规划（最多 3 轮） |
| LG-04 | 进度实时反馈 | P1 | 通过 WebSocket 推送每一步的执行状态（pending/running/done/failed） |
| LG-05 | 人工确认节点 | P2 | 涉及危险操作（删除文件、写数据库）时暂停等待用户确认 |

### 2.7 用户管理（基础版）

| ID | 功能点 | 优先级 | 验收标准 |
|----|--------|--------|----------|
| UM-01 | 会话隔离 | P0 | 不同 session_id 的对话上下文完全隔离 |
| UM-02 | 知识库归属 | P1 | 所有上传文档关联到当前用户（单用户默认关联 default_user） |

---

## 3. 非功能需求

### 3.1 性能

| 指标 | 目标 | 说明 |
|------|------|------|
| 首次回答延迟（非 RAG） | < 3s | 从请求到第一个 token 返回 |
| 首次回答延迟（RAG） | < 5s | 含向量检索 + 图谱查询耗时 |
| 流式 token 间隔 | < 100ms/token | WebSocket 推送延迟 |
| 文件上传处理 | < 30s（50MB PDF） | 含解析 + 分块 + 向量化 |
| 并发对话 | ≥ 5 并发 session | 本地单机部署 |

### 3.2 数据隐私

- **本地优先**：所有数据（文档、向量、对话）存储在本地；LLM 调用可选本地模型（Ollama）或脱敏后的云端 API
- **敏感信息过滤**：上传文档时可选择自动识别并脱敏手机号、身份证号、邮箱
- **数据删除**：删除文档时级联清除向量、图谱节点，不留残留数据

### 3.3 可扩展性

- **工具热插拔**：新增工具只需继承 `BaseTool` 并放入 tools 目录，启动时自动注册
- **Skill 热插拔**：新增 Skill 继承 `BaseSkill` 并放入 skills 目录
- **MCP Server 动态注册**：运行时通过 API 注册/注销 MCP Server，无需重启
- **模型可替换**：通过配置切换 LLM（Qwen/DeepSeek/GPT）、Embedding 模型
- **向量数据库可替换**：ChromaDB → Milvus/Qdrant 只需修改配置和适配器

### 3.4 技术约束

- Python 3.11+
- FastAPI 异步框架
- LangChain ≥ 0.3, LangGraph ≥ 0.2
- 默认使用 Qwen 系列模型（兼容 OpenAI API 格式）
- 前端 Vue 3 + Composition API + JS（非 TS）

---

## 4. 数据模型设计

### 4.1 核心实体

```
┌─────────────────────────────────────────────────────────────┐
│                        核心实体关系图                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────┐    1:N    ┌──────────┐                        │
│  │  User    │──────────▶│ Session  │                        │
│  └──────────┘           └──────────┘                        │
│       │                     │ 1:N                           │
│       │                     ▼                               │
│       │                 ┌──────────┐                        │
│       │                 │ Message  │                        │
│       │                 └──────────┘                        │
│       │                                                     │
│       │ 1:N    ┌──────────────┐                             │
│       └───────▶│ KnowledgeDoc │                             │
│                └──────────────┘                             │
│                      │ 1:N                                  │
│                      ▼                                      │
│                ┌──────────────┐                             │
│                │ DocChunk     │  (向量存储在 ChromaDB)       │
│                └──────────────┘                             │
│                      │                                      │
│                      │ N:M (通过 Neo4j 关联)                │
│                      ▼                                      │
│                ┌──────────────┐    ┌──────────────┐         │
│                │  Entity      │───▶│ Relation     │         │
│                └──────────────┘    └──────────────┘         │
│                                                             │
│  ┌──────────┐           ┌──────────┐                        │
│  │ Tool     │           │ Skill    │                        │
│  └──────────┘           └──────────┘                        │
│                                                             │
│  ┌──────────────┐        ┌──────────────────┐               │
│  │ MCPServer    │───1:N──▶ MCPTool          │               │
│  └──────────────┘        └──────────────────┘               │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 4.2 实体定义

#### User（用户）
| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| username | VARCHAR(64) | 用户名，默认 "default_user" |
| preferences | JSON | 偏好设置（默认模型、语言等） |
| created_at | DATETIME | 创建时间 |

#### Session（会话）
| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| user_id | UUID → User | 所属用户 |
| title | VARCHAR(256) | 会话标题（自动生成或手动设置） |
| mode | ENUM | `normal` / `rag` / `graph` |
| status | ENUM | `active` / `archived` |
| created_at | DATETIME | 创建时间 |
| updated_at | DATETIME | 最后活跃时间 |

#### Message（消息）
| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| session_id | UUID → Session | 所属会话 |
| role | ENUM | `user` / `assistant` / `system` / `tool` |
| content | TEXT | 消息正文 |
| metadata | JSON | 来源引用、token 数、延迟等 |
| created_at | DATETIME | 消息时间 |

#### KnowledgeDoc（知识库文档）
| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| user_id | UUID → User | 所属用户 |
| filename | VARCHAR(512) | 原始文件名 |
| file_type | VARCHAR(32) | pdf/docx/xlsx/txt/md/image |
| file_size | INT | 字节数 |
| file_path | VARCHAR(1024) | 本地存储路径 |
| status | ENUM | `uploading` / `parsing` / `chunking` / `embedding` / `done` / `failed` |
| chunk_count | INT | 分块数量 |
| category | VARCHAR(128) | 分类标签（可选） |
| created_at | DATETIME | 上传时间 |

#### DocChunk（文档分块 — 向量存储在 ChromaDB）
| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| doc_id | UUID → KnowledgeDoc | 所属文档 |
| chunk_index | INT | 分块序号 |
| content | TEXT | 文本内容 |
| metadata | JSON | 页码、标题等 |

#### Entity / Relation（知识图谱 — 存储在 Neo4j）
- **Entity**: id, name, type (PERSON/ORG/LOCATION/TECH/...), properties (JSON)
- **Relation**: source_entity → target_entity, relation_type (BELONGS_TO/DEPENDS_ON/CREATED_BY/...), properties (JSON)

#### Tool（工具）
| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| name | VARCHAR(128) | 工具名称 |
| description | TEXT | 工具描述（LLM 选择依据） |
| tool_type | ENUM | `builtin` / `mcp` |
| parameters_schema | JSON | JSON Schema 格式的参数定义 |
| enabled | BOOL | 是否启用 |

#### Skill（技能）
| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| name | VARCHAR(128) | Skill 名称 |
| description | TEXT | 描述 |
| entry_point | VARCHAR(256) | 入口函数/类路径 |
| enabled | BOOL | 是否启用 |

#### MCPServer（MCP 服务）
| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| name | VARCHAR(128) | 别名 |
| transport | ENUM | `stdio` / `sse` |
| command | VARCHAR(512) | stdio 模式下的启动命令 |
| url | VARCHAR(512) | SSE 模式下的 URL |
| status | ENUM | `connected` / `disconnected` / `error` |
| registered_at | DATETIME | 注册时间 |

---

# 第二部分：API 接口文档

## 通用约定

- **Base URL**: `http://localhost:8000/api`
- **认证**: 单用户模式，暂无需认证 Token；预留 `X-User-ID` Header
- **响应格式**: `{ "code": 0, "data": {...}, "message": "ok" }`
- **错误响应**: `{ "code": <error_code>, "data": null, "message": "<error_msg>" }`
- **分页格式**: `{ "code": 0, "data": { "items": [...], "total": 100, "page": 1, "page_size": 20 } }`

---

## 1. 知识库模块

### 1.1 POST /api/knowledge/upload

上传文件到知识库。

**Request**: `multipart/form-data`

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| file | file | 是 | 文件（PDF/Word/Excel/TXT/Markdown/图片） |
| category | string | 否 | 分类标签 |

**Response** (201):

```json
{
  "code": 0,
  "data": {
    "doc_id": "uuid",
    "filename": "技术方案.pdf",
    "file_type": "pdf",
    "file_size": 2048000,
    "status": "uploading"
  }
}
```

**处理流程**: 上传 → 异步解析分块 → 向量化 → 更新 `status=done`

---

### 1.2 GET /api/knowledge/list

获取知识库文档列表。

**Request**:

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| page | int | 否 | 1 | 页码 |
| page_size | int | 否 | 20 | 每页数量 (max 100) |
| category | string | 否 | - | 分类筛选 |
| file_type | string | 否 | - | 文件类型筛选 |
| status | string | 否 | - | 状态筛选 |

**Response** (200):

```json
{
  "code": 0,
  "data": {
    "items": [
      {
        "doc_id": "uuid",
        "filename": "技术方案.pdf",
        "file_type": "pdf",
        "file_size": 2048000,
        "status": "done",
        "chunk_count": 42,
        "category": "技术文档",
        "created_at": "2026-05-10T10:30:00Z"
      }
    ],
    "total": 15,
    "page": 1,
    "page_size": 20
  }
}
```

---

### 1.3 GET /api/knowledge/{doc_id}

获取单个文档详情。

**Response** (200):

```json
{
  "code": 0,
  "data": {
    "doc_id": "uuid",
    "filename": "技术方案.pdf",
    "file_type": "pdf",
    "file_size": 2048000,
    "status": "done",
    "chunk_count": 42,
    "category": "技术文档",
    "created_at": "2026-05-10T10:30:00Z",
    "chunks": [
      { "chunk_index": 0, "content": "...", "metadata": { "page": 1 } }
    ]
  }
}
```

---

### 1.4 DELETE /api/knowledge/{doc_id}

删除文档（级联删除向量数据 + 关联图谱节点）。

**Response** (200):

```json
{
  "code": 0,
  "data": { "deleted": true, "doc_id": "uuid" }
}
```

---

### 1.5 POST /api/knowledge/graph/build

对指定文档构建知识图谱。

**Request** (JSON):

```json
{
  "doc_id": "uuid"
}
```

**Response** (200):

```json
{
  "code": 0,
  "data": {
    "doc_id": "uuid",
    "entities_extracted": 35,
    "relations_extracted": 28,
    "status": "done"
  }
}
```

---

### 1.6 GET /api/knowledge/graph/query

查询知识图谱子图。

**Request**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| keyword | string | 是 | 查询关键字（实体名） |
| depth | int | 否 | 跳数，默认 1 |
| limit | int | 否 | 最大节点数，默认 50 |

**Response** (200):

```json
{
  "code": 0,
  "data": {
    "nodes": [
      { "id": "e1", "name": "LangChain", "type": "TECH", "properties": {} }
    ],
    "edges": [
      { "source": "e1", "target": "e2", "relation_type": "DEPENDS_ON" }
    ]
  }
}
```

---

## 2. 对话模块

### 2.1 POST /api/chat/session/create

创建新会话。

**Request** (JSON):

```json
{
  "title": "技术方案讨论",
  "mode": "rag"
}
```

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| title | string | 否 | "新对话" | 会话标题 |
| mode | string | 否 | "normal" | `normal` / `rag` |

**Response** (201):

```json
{
  "code": 0,
  "data": {
    "session_id": "uuid",
    "title": "技术方案讨论",
    "mode": "rag",
    "created_at": "2026-05-10T10:30:00Z"
  }
}
```

---

### 2.2 GET /api/chat/session/list

获取会话列表。

**Request**:

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| page | int | 否 | 1 | 页码 |
| page_size | int | 否 | 20 | 每页数量 |
| status | string | 否 | - | `active` / `archived` |

**Response** (200):

```json
{
  "code": 0,
  "data": {
    "items": [
      {
        "session_id": "uuid",
        "title": "技术方案讨论",
        "mode": "rag",
        "message_count": 14,
        "created_at": "2026-05-10T10:30:00Z",
        "updated_at": "2026-05-10T11:00:00Z"
      }
    ],
    "total": 8,
    "page": 1,
    "page_size": 20
  }
}
```

---

### 2.3 DELETE /api/chat/session/{session_id}

删除会话及所有关联消息。

**Response** (200):

```json
{
  "code": 0,
  "data": { "deleted": true, "session_id": "uuid" }
}
```

---

### 2.4 POST /api/chat/message

发送消息（支持流式/非流式）。

**Request** (JSON):

```json
{
  "session_id": "uuid",
  "content": "请总结一下技术方案的核心要点",
  "mode": "rag",
  "stream": true,
  "use_memory": true
}
```

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| session_id | string | 是 | - | 会话 ID |
| content | string | 是 | - | 用户消息 |
| mode | string | 否 | "normal" | `normal` / `rag` |
| stream | bool | 否 | true | 是否流式 |
| use_memory | bool | 否 | false | 是否使用长期记忆 |

**Response** — 非流式 (200):

```json
{
  "code": 0,
  "data": {
    "message_id": "uuid",
    "role": "assistant",
    "content": "技术方案的核心要点包括...",
    "sources": [
      { "doc_id": "uuid", "filename": "技术方案.pdf", "chunk_index": 3, "relevance": 0.92, "excerpt": "..." }
    ],
    "token_count": 450,
    "created_at": "2026-05-10T11:05:00Z"
  }
}
```

**Response** — 流式：通过 WebSocket 推送。

详见 [2.8 WebSocket 消息协议](#28-websocket-消息协议)。

---

### 2.5 GET /api/chat/message/{session_id}/history

获取会话历史消息。

**Request**:

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| page | int | 否 | 1 | 页码 |
| page_size | int | 否 | 50 | 每页数量 |
| before | string | 否 | - | 早于此消息 ID 的历史（游标翻页） |

**Response** (200):

```json
{
  "code": 0,
  "data": {
    "items": [
      {
        "message_id": "uuid",
        "role": "user",
        "content": "请总结一下技术方案的核心要点",
        "created_at": "2026-05-10T11:04:30Z"
      },
      {
        "message_id": "uuid",
        "role": "assistant",
        "content": "技术方案的核心要点包括...",
        "sources": [...],
        "token_count": 450,
        "created_at": "2026-05-10T11:05:00Z"
      }
    ],
    "total": 14,
    "page": 1,
    "page_size": 50
  }
}
```

---

### 2.6 PATCH /api/chat/session/{session_id}

更新会话（重命名/归档/切换模式）。

**Request** (JSON):

```json
{
  "title": "新标题",
  "status": "archived"
}
```

**Response** (200):

```json
{
  "code": 0,
  "data": { "session_id": "uuid", "title": "新标题", "status": "archived" }
}
```

---

### 2.7 WS /api/chat/ws/{session_id}

WebSocket 流式对话连接。

**连接参数**: 在 URL 中携带 `session_id`

**使用方式**: 建立 WS 连接后，发送 JSON 消息进行对话，接收流式 token 推送。

详见下方协议说明。

---

### 2.8 WebSocket 消息协议

#### 客户端 → 服务端

```json
{
  "type": "chat",
  "content": "请总结一下技术方案",
  "mode": "rag",
  "use_memory": false
}
```

```json
{
  "type": "stop",
  "reason": "user_cancel"
}
```

#### 服务端 → 客户端

**token 推送**:
```json
{ "type": "token", "data": "技术" }
{ "type": "token", "data": "方案" }
```

**来源引用**:
```json
{
  "type": "sources",
  "data": [
    { "doc_id": "uuid", "filename": "xxx.pdf", "excerpt": "...", "relevance": 0.92 }
  ]
}
```

**完成**:
```json
{ "type": "done", "data": { "message_id": "uuid", "token_count": 450 } }
```

**错误**:
```json
{ "type": "error", "data": { "code": 5001, "message": "检索服务不可用" } }
```

**进度反馈（LangGraph 任务执行）**:
```json
{
  "type": "progress",
  "data": { "step": 2, "total_steps": 5, "status": "running", "description": "正在查询知识库..." }
}
```

---

## 3. 工具与 Skill 模块

### 3.1 GET /api/tools/list

获取可用工具列表。

**Response** (200):

```json
{
  "code": 0,
  "data": {
    "items": [
      {
        "tool_id": "uuid",
        "name": "calculator",
        "description": "执行数学计算",
        "tool_type": "builtin",
        "parameters_schema": {
          "type": "object",
          "properties": {
            "expression": { "type": "string", "description": "数学表达式" }
          },
          "required": ["expression"]
        },
        "enabled": true
      }
    ]
  }
}
```

---

### 3.2 GET /api/skills/list

获取可用 Skill 列表。

**Response** (200):

```json
{
  "code": 0,
  "data": {
    "items": [
      {
        "skill_id": "uuid",
        "name": "pdf-summarizer",
        "description": "生成 PDF 文档摘要",
        "enabled": true
      }
    ]
  }
}
```

---

### 3.3 POST /api/skills/execute

手动触发 Skill 执行。

**Request** (JSON):

```json
{
  "skill_name": "pdf-summarizer",
  "params": {
    "doc_id": "uuid"
  }
}
```

**Response** (200):

```json
{
  "code": 0,
  "data": {
    "execution_id": "uuid",
    "skill_name": "pdf-summarizer",
    "status": "running",
    "result": null
  }
}
```

---

### 3.4 GET /api/skills/execute/{execution_id}

查询 Skill 执行状态和结果。

**Response** (200):

```json
{
  "code": 0,
  "data": {
    "execution_id": "uuid",
    "skill_name": "pdf-summarizer",
    "status": "done",
    "result": { "summary": "...", "key_points": ["..."] },
    "started_at": "2026-05-10T11:05:00Z",
    "finished_at": "2026-05-10T11:05:15Z"
  }
}
```

---

## 4. MCP 管理模块

### 4.1 POST /api/mcp/server/register

注册 MCP Server。

**Request** (JSON) — stdio 方式:

```json
{
  "name": "sqlite-query",
  "transport": "stdio",
  "command": "python",
  "args": ["-m", "mcp_server_sqlite", "--db-path", "/data/app.db"]
}
```

**Request** (JSON) — SSE 方式:

```json
{
  "name": "rest-api-mcp",
  "transport": "sse",
  "url": "http://localhost:3001/sse"
}
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| name | string | 是 | 别名，唯一 |
| transport | string | 是 | `stdio` 或 `sse` |
| command | string | stdio 必填 | 启动命令 |
| args | string[] | 否 | 命令参数列表 |
| env | object | 否 | 环境变量 |
| url | string | sse 必填 | SSE 端点 URL |

**Response** (201):

```json
{
  "code": 0,
  "data": {
    "server_id": "uuid",
    "name": "sqlite-query",
    "transport": "stdio",
    "status": "connected",
    "tools_discovered": 2,
    "registered_at": "2026-05-10T11:05:00Z"
  }
}
```

---

### 4.2 GET /api/mcp/server/list

获取已注册 MCP Server 列表。

**Response** (200):

```json
{
  "code": 0,
  "data": {
    "items": [
      {
        "server_id": "uuid",
        "name": "sqlite-query",
        "transport": "stdio",
        "status": "connected",
        "tools_count": 2,
        "registered_at": "2026-05-10T11:05:00Z"
      }
    ]
  }
}
```

---

### 4.3 GET /api/mcp/server/{server_id}

获取 MCP Server 详情（含提供的工具列表）。

**Response** (200):

```json
{
  "code": 0,
  "data": {
    "server_id": "uuid",
    "name": "sqlite-query",
    "transport": "stdio",
    "command": "python -m mcp_server_sqlite --db-path /data/app.db",
    "status": "connected",
    "tools": [
      {
        "name": "execute_sql",
        "description": "Execute a SQL query against the SQLite database",
        "parameters_schema": {
          "type": "object",
          "properties": {
            "query": { "type": "string", "description": "SQL query to execute" }
          },
          "required": ["query"]
        }
      }
    ],
    "registered_at": "2026-05-10T11:05:00Z"
  }
}
```

---

### 4.4 DELETE /api/mcp/server/{server_id}

移除（注销）MCP Server。

**Response** (200):

```json
{
  "code": 0,
  "data": { "deleted": true, "server_id": "uuid" }
}
```

---

### 4.5 POST /api/mcp/server/{server_id}/reconnect

重新连接 MCP Server。

**Response** (200):

```json
{
  "code": 0,
  "data": { "server_id": "uuid", "status": "connected" }
}
```

---

## 5. 任务规划模块

### 5.1 POST /api/task/plan

提交复杂任务，返回执行计划。

**Request** (JSON):

```json
{
  "session_id": "uuid",
  "task": "分析技术方案.pdf，提取其中提到的所有技术名词并解释，最后生成一份技术选型建议",
  "mode": "rag"
}
```

**Response** (200):

```json
{
  "code": 0,
  "data": {
    "task_id": "uuid",
    "status": "planning",
    "plan": [
      { "step": 1, "action": "search_knowledge", "description": "检索"技术方案.pdf"中技术名词", "params": {} },
      { "step": 2, "action": "extract_entities", "description": "提取技术名词实体", "params": {} },
      { "step": 3, "action": "search_web_or_kb", "description": "查询每个技术名词的详细解释", "params": {} },
      { "step": 4, "action": "generate_report", "description": "生成技术选型建议报告", "params": {} }
    ]
  }
}
```

---

### 5.2 GET /api/task/{task_id}/status

查询任务执行状态与进度。

**Response** (200):

```json
{
  "code": 0,
  "data": {
    "task_id": "uuid",
    "status": "running",
    "current_step": 2,
    "total_steps": 4,
    "steps": [
      { "step": 1, "status": "done", "result": "检索到 15 个相关文档片段" },
      { "step": 2, "status": "running", "result": null },
      { "step": 3, "status": "pending", "result": null },
      { "step": 4, "status": "pending", "result": null }
    ]
  }
}
```

---

## 6. 错误码

| 错误码 | 说明 |
|--------|------|
| 0 | 成功 |
| 1001 | 参数校验失败 |
| 2001 | 文件格式不支持 |
| 2002 | 文件过大 |
| 2003 | 文档不存在 |
| 3001 | 会话不存在 |
| 3002 | 会话已归档 |
| 4001 | MCP Server 连接失败 |
| 4002 | MCP Server 已存在 |
| 4003 | MCP Server 不存在 |
| 5001 | 向量检索失败 |
| 5002 | 知识图谱查询失败 |
| 5003 | LLM 调用失败 |
| 9999 | 内部错误 |

---

# 第三部分：LangGraph 工作流设计

## 1. 整体架构

```
                        ┌─────────────────────────┐
                        │    FastAPI Application   │
                        └───────────┬─────────────┘
                                    │
                        ┌───────────▼─────────────┐
                        │   LangGraph Supervisor   │
                        │   (任务路由/调度)         │
                        └───────────┬─────────────┘
                                    │
          ┌─────────────────────────┼─────────────────────────┐
          │                         │                         │
  ┌───────▼───────┐         ┌───────▼───────┐         ┌───────▼───────┐
  │  Simple Chat   │         │  RAG Pipeline  │         │  Task Planner  │
  │  Graph         │         │  Graph         │         │  Graph         │
  └───────────────┘         └───────────────┘         └───────────────┘
```

系统包含三个 LangGraph 工作流：

1. **SimpleChatGraph** — 普通对话
2. **RAGChatGraph** — 知识增强对话
3. **TaskPlannerGraph** — 复杂任务规划与执行（Plan → Execute → Reflect 循环）

---

## 2. SimpleChatGraph（普通对话）

```
┌──────────┐     ┌──────────────┐     ┌──────────┐     ┌──────────┐
│  START   │────▶│ BuildContext │────▶│   LLM    │────▶│   END    │
│          │     │   Node       │     │  Node    │     │          │
└──────────┘     └──────────────┘     └──────────┘     └──────────┘
```

### 节点定义

#### BuildContextNode
```python
class BuildContextNode:
    """
    构建对话上下文：
    1. 从 Redis 获取短期记忆（当前 session 最近 N 轮）
    2. 如果 use_memory=True，从 ChromaDB 获取用户画像
    3. 拼接为 LangChain Messages 列表
    """
    inputs:  session_id, user_message, use_memory
    outputs: messages (List[BaseMessage]), context_metadata
```

#### LLMNode
```python
class LLMNode:
    """
    调用 LLM 生成回复：
    1. 封装 system prompt
    2. 传入 messages 列表
    3. 流式输出 token → WebSocket 推送
    4. 完成后保存消息到 MySQL
    """
    inputs:  messages, model_config
    outputs: response, token_count
```

### 边（Edges）

| 起点 | 终点 | 条件 |
|------|------|------|
| START | BuildContextNode | 无条件 |
| BuildContextNode | LLMNode | 无条件 |
| LLMNode | END | 无条件 |

---

## 3. RAGChatGraph（知识增强对话）

```
                              ┌─────────────────────┐
                              │    知识检索 (并行)    │
                              ├─────────────────────┤
                              │  VectorRetrieval    │──▶ ChromaDB
                              │  GraphRetrieval     │──▶ Neo4j
                              └─────────┬───────────┘
                                        │
┌──────────┐     ┌──────────────┐     ┌─▼──────────┐     ┌──────────────┐     ┌──────────┐
│  START   │────▶│ BuildContext │────▶│  Retrieval  │────▶│  Rerank &    │────▶│   END    │
│          │     │   Node       │     │  Router     │     │  Generate    │     │          │
└──────────┘     └──────────────┘     └─────────────┘     └──────────────┘     └──────────┘
```

### 节点定义

#### BuildContextNode
```python
class BuildContextNode:
    """
    与 SimpleChatGraph 相同：构建对话上下文 + 用户画像
    """
    inputs:  session_id, user_message, use_memory
    outputs: messages, rewritten_query (LLM 改写后的搜索查询)
```

#### RetrievalRouter
```python
class RetrievalRouter:
    """
    并行执行两种检索：
    1. 向量检索 (ChromaDB): user_message → embedding → top_k=5 相似 chunk
    2. 图谱检索 (Neo4j): user_message → NER 提取实体 → 查 1-hop 子图
    """
    inputs:  rewritten_query, retrieval_config (top_k, depth, threshold)
    outputs: vector_results (List[DocChunk]), graph_results (subgraph nodes + edges)
```

#### RerankAndGenerateNode
```python
class RerankAndGenerateNode:
    """
    1. 对检索结果重排序（可选 BGE-Reranker 或 LLM-based）
    2. 拼接上下文: system_prompt + 检索结果 + 对话历史 + 用户消息
    3. 调用 LLM 生成回复
    4. 附带来源引用
    """
    inputs:  messages, vector_results, graph_results
    outputs: response, sources, token_count
```

### 边（Edges）

| 起点 | 终点 | 条件 |
|------|------|------|
| START | BuildContextNode | 无条件 |
| BuildContextNode | RetrievalRouter | 无条件 |
| RetrievalRouter | RerankAndGenerateNode | 无条件 |
| RerankAndGenerateNode | END | 无条件 |

### 条件分支（路由逻辑）

在 `RetrievalRouter` 内部，根据检索结果决定行为：

```python
def should_retry_or_proceed(state):
    if len(state.vector_results) == 0 and len(state.graph_results["nodes"]) == 0:
        return "rewrite_query"  # 无结果 → 改写查询重试
    return "generate"           # 有结果 → 生成回复
```

---

## 4. TaskPlannerGraph（任务规划与执行）

这是核心的 Plan → Execute → Reflect 循环。

```
                    ┌────────────────────────────────────────────────┐
                    │              TaskPlannerGraph                  │
                    │                                                │
 ┌──────────┐       ┌──────────┐     ┌──────────┐     ┌──────────┐  │
 │  START   │──────▶│   Plan   │────▶│ Execute  │────▶│ Reflect  │──┼─▶ END
 │          │       │   Node   │     │  Node    │     │  Node    │  │
 └──────────┘       └──────────┘     └──────────┘     └──────────┘  │
                         ▲                 │               │         │
                         │                 │               ├─ pass ──┘
                         │                 │               │
                         └─── replan ──────┘               └─ fail ──▶ (retry or replan)
                         │                                           │
                         └───────────────────────────────────────────┘
                    │                                                │
                    └────────────────────────────────────────────────┘
```

### 状态定义（GraphState）

```python
from typing import TypedDict, List, Optional, Literal, Annotated
from langgraph.graph.message import add_messages

class TaskState(TypedDict):
    # 原始输入
    session_id: str
    user_task: str               # 用户原始请求
    mode: str                    # "normal" | "rag"

    # 对话上下文
    messages: Annotated[list, add_messages]

    # 规划
    plan: List[Step]             # 执行计划
    current_step_index: int      # 当前步骤索引
    max_retries: int             # 最大重试次数 (default 3)
    retry_count: int             # 当前重试次数

    # 执行
    execution_results: List[StepResult]  # 每步执行结果

    # 状态
    status: Literal["planning", "executing", "reflecting", "done", "failed"]
```

```python
class Step(TypedDict):
    step_id: int
    action: str                  # "search_knowledge" | "call_tool" | "call_llm" | "call_skill"
    description: str             # 人类可读的描述
    params: dict                 # 动作参数
    depends_on: List[int]        # 依赖的前置步骤 ID
```

```python
class StepResult(TypedDict):
    step_id: int
    status: Literal["pending", "running", "done", "failed"]
    output: Optional[str]
    error: Optional[str]
    started_at: Optional[str]
    finished_at: Optional[str]
```

### 节点定义

#### PlanNode
```python
class PlanNode:
    """
    将用户复杂任务拆解为步骤列表：
    1. 构造 prompt: "你是一个任务规划器。请将以下用户请求拆解为可执行的步骤..."
    2. LLM 返回结构化 JSON: [{step_id, action, description, params, depends_on}, ...]
    3. 验证计划的合理性和步骤依赖
    4. 通过 WebSocket 推送计划给前端
    """
    inputs:  user_task, messages, mode, available_tools, available_skills
    outputs: plan (List[Step]), status="executing"
```

#### ExecuteNode
```python
class ExecuteNode:
    """
    按计划逐步执行：
    1. 获取当前步骤（plan[current_step_index]）
    2. 根据 action 类型分发:
       - "search_knowledge" → RAG 检索
       - "call_tool"       → 工具调用（含 MCP）
       - "call_llm"        → LLM 生成
       - "call_skill"      → Skill 执行
    3. 记录中间结果到 execution_results
    4. 通过 WebSocket 推送进度
    """
    inputs:  plan, current_step_index, execution_results
    outputs: execution_results (updated), current_step_index+1
```

#### ReflectNode
```python
class ReflectNode:
    """
    评估已执行步骤的结果：
    1. 检查所有步骤状态
    2. 如果全部 done → status="done" → 路由到 END
    3. 如果有 failed 步骤:
       - retry_count < max_retries → 重试失败步骤 → 路由回 ExecuteNode
       - retry_count >= max_retries → 路由回 PlanNode（重新规划）
    4. 如果结果不完整 → 路由回 PlanNode 补充步骤
    """
    inputs:  execution_results, retry_count, max_retries
    outputs: status, retry_count, routing_decision
```

### 边（Edges）

| 起点 | 终点 | 条件 |
|------|------|------|
| START | PlanNode | 无条件 |
| PlanNode | ExecuteNode | PlanNode 完成规划后 |
| ExecuteNode | ReflectNode | 所有步骤执行完毕 |
| ReflectNode | END | `status == "done"` |
| ReflectNode | ExecuteNode | 有步骤失败且 `retry_count < max_retries`（重试） |
| ReflectNode | PlanNode | 步骤全部失败或 `retry_count >= max_retries`（重新规划） |

### 条件路由函数

```python
def route_after_reflect(state: TaskState) -> str:
    if state["status"] == "done":
        return "end"

    failed_steps = [s for s in state["execution_results"] if s["status"] == "failed"]

    if not failed_steps:
        # 没有失败步骤但状态不是 done → 可能缺少步骤，重新规划
        return "plan"

    if state["retry_count"] < state["max_retries"]:
        # 仅重试失败的步骤
        return "execute"

    # 超过最大重试次数，重新规划
    return "plan"
```

### 进度推送机制

在每个节点内部，通过回调向 WebSocket 推送进度：

```python
async def push_progress(state: TaskState, ws_manager, session_id):
    await ws_manager.send(session_id, {
        "type": "progress",
        "data": {
            "current_step": state["current_step_index"] + 1,
            "total_steps": len(state["plan"]),
            "status": "running",
            "description": state["plan"][state["current_step_index"]]["description"],
            "steps": [
                {
                    "step": r["step_id"],
                    "status": r["status"],
                    "description": state["plan"][i]["description"]
                }
                for i, r in enumerate(state["execution_results"])
            ]
        }
    })
```

---

## 5. 对话路由（Supervisor）

在应用入口，根据用户请求类型路由到不同的 Graph：

```python
class SupervisorRouter:
    """
    判断用户请求类型，路由到对应 Graph：
    1. 简单对话 → SimpleChatGraph
    2. 知识库问答 → RAGChatGraph
    3. 复杂任务 → TaskPlannerGraph
    """

    def route(self, user_message: str, mode: str) -> str:
        # mode 优先：用户显式选择了模式
        if mode == "rag":
            # 进一步判断是否需要规划
            if self._is_complex_task(user_message):
                return "task_planner_graph"
            return "rag_chat_graph"

        if mode == "normal":
            return "simple_chat_graph"

        # 自动检测：如果消息包含"步骤"/"先...再..."/"然后"等关键词
        # 或者 LLM 快速分类判断复杂度
        return self._auto_classify(user_message)

    def _is_complex_task(self, message: str) -> bool:
        """通过关键词或快速 LLM 分类判断是否为复杂任务"""
        complex_keywords = ["步骤", "先", "再", "然后", "最后", "计划", "分析并", "比较", "整理"]
        return any(kw in message for kw in complex_keywords)
```

---

## 6. Graph 编译与运行

```python
from langgraph.graph import StateGraph, END

def build_simple_chat_graph():
    graph = StateGraph(ChatState)
    graph.add_node("build_context", BuildContextNode())
    graph.add_node("llm", LLMNode())
    graph.set_entry_point("build_context")
    graph.add_edge("build_context", "llm")
    graph.add_edge("llm", END)
    return graph.compile()

def build_rag_chat_graph():
    graph = StateGraph(RAGState)
    graph.add_node("build_context", BuildContextNode())
    graph.add_node("retrieval", RetrievalRouter())
    graph.add_node("rerank_generate", RerankAndGenerateNode())
    graph.set_entry_point("build_context")
    graph.add_edge("build_context", "retrieval")
    graph.add_edge("retrieval", "rerank_generate")
    graph.add_edge("rerank_generate", END)
    return graph.compile()

def build_task_planner_graph():
    graph = StateGraph(TaskState)
    graph.add_node("plan", PlanNode())
    graph.add_node("execute", ExecuteNode())
    graph.add_node("reflect", ReflectNode())

    graph.set_entry_point("plan")
    graph.add_edge("plan", "execute")
    graph.add_edge("execute", "reflect")

    graph.add_conditional_edges(
        "reflect",
        route_after_reflect,
        {
            "end": END,
            "execute": "execute",
            "plan": "plan",
        }
    )
    return graph.compile()
```

---

## 7. 文件结构建议

```
personal-agent/
├── app/
│   ├── api/
│   │   ├── chat.py              # 对话相关 API
│   │   ├── knowledge.py         # 知识库相关 API
│   │   ├── mcp.py               # MCP 管理 API
│   │   ├── skills.py            # Skill API
│   │   └── tasks.py             # 任务规划 API
│   ├── core/
│   │   ├── config.py            # 配置管理
│   │   ├── database.py          # MySQL 连接
│   │   └── redis_client.py      # Redis 连接
│   ├── graphs/
│   │   ├── supervisor.py        # 对话路由器
│   │   ├── simple_chat.py       # 普通对话 Graph
│   │   ├── rag_chat.py          # RAG 对话 Graph
│   │   └── task_planner.py      # 任务规划 Graph
│   ├── models/
│   │   ├── chat.py              # 对话 ORM 模型
│   │   ├── knowledge.py         # 知识库 ORM 模型
│   │   └── mcp.py               # MCP ORM 模型
│   ├── services/
│   │   ├── embedding.py         # 向量化服务 (Qwen)
│   │   ├── vector_store.py      # ChromaDB 操作
│   │   ├── graph_store.py       # Neo4j 操作
│   │   ├── ocr.py               # OCR 服务
│   │   ├── file_parser.py       # 文件解析 (PDF/Word/Excel)
│   │   └── llm.py               # LLM 调用封装
│   ├── mcp/
│   │   ├── manager.py           # MCP Server 生命周期管理
│   │   └── client.py            # MCP 客户端
│   ├── tools/
│   │   ├── base.py              # BaseTool 抽象
│   │   └── builtin/             # 内置工具
│   ├── skills/
│   │   ├── base.py              # BaseSkill 抽象
│   │   └── builtin/             # 内置 Skill
│   └── ws/
│       └── manager.py           # WebSocket 连接管理
├── frontend/                    # Vue 3 前端
├── requirements.txt
├── .env
└── DESIGN_DOC.md
```
