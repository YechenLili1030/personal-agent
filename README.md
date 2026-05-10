# PersonalAgent

个人智能助手系统 — 基于 LangChain + LangGraph + FastAPI + Vue 3。

## 功能

- **RAG 知识库问答** — 上传 PDF/Word/Excel/图片，自动向量化 + 知识图谱存储，对话时检索增强
- **多格式文件解析** — PDF（含扫描件多模态提取）、Word（含文本框）、Excel、Markdown、图片 OCR
- **工具调用** — 内置天气查询、日期获取等 Tool，LLM 自主决定调用
- **流式对话** — WebSocket 实时推送，支持 normal / RAG 双模式切换
- **自动文档摘要** — 上传后 AI 自动生成文档摘要，注入到每个 chunk 元数据

## 技术栈

| 层 | 技术 |
|---|------|
| 后端框架 | FastAPI |
| Agent 框架 | LangChain + LangGraph |
| 对话 LLM | DeepSeek (deepseek-v4-flash) |
| 向量化 | 百炼 text-embedding-v4 |
| 多模态 | 百炼 qwen3.6-flash |
| 向量数据库 | ChromaDB |
| 关系数据库 | MySQL 8.0 |
| 前端 | Vue 3 + JS + Vite |

## 快速开始

### 环境要求

- Python 3.11+
- Node.js 20+
- MySQL 8.0

### 安装

```bash
# 克隆仓库
git clone https://github.com/你的用户名/personal-agent.git
cd personal-agent

# 创建虚拟环境
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Mac/Linux

# 安装后端依赖
pip install -r backend/requirements.txt

# 安装前端依赖
cd frontend && npm install && cd ..
```

### 配置

```bash
# 复制环境变量模板，填入你的 API Key
cp .env.example .env
```

### 初始化数据库

```bash
mysql -u root -p < sql/init.sql
```

### 启动

```bash
# 终端1：后端
cd backend
python main.py

# 终端2：前端
cd frontend
npm run dev
```

- 后端：http://localhost:8000 （Swagger：/docs）
- 前端：http://localhost:5173
- 默认账号：admin / admin123

## 项目结构

```
personal-agent/
├── backend/
│   ├── main.py                 # 启动入口
│   └── app/
│       ├── api/                # FastAPI 路由
│       │   ├── auth.py         # 登录
│       │   ├── chat.py         # 对话（REST + WebSocket）
│       │   └── knowledge.py    # 知识库
│       ├── core/               # 配置、数据库、日志、提示词
│       ├── models/             # SQLAlchemy ORM
│       ├── services/           # 核心业务逻辑
│       ├── tools/              # LangChain Tool
│       └── main.py             # FastAPI 应用定义
├── frontend/
│   └── src/
│       ├── views/              # Login / Chat / Knowledge
│       └── components/         # ConfirmModal
├── sql/
│   └── init.sql                # 建表脚本
└── .env.example                # 环境变量模板
```
