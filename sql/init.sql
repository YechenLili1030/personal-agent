-- ============================================
-- PersonalAgent 数据库初始化脚本
-- MySQL 8.0+
-- 连接: localhost:3306  root / mikasa2001
-- ============================================

CREATE DATABASE IF NOT EXISTS personal_agent
    DEFAULT CHARACTER SET utf8mb4
    DEFAULT COLLATE utf8mb4_unicode_ci;

USE personal_agent;

-- ============================================
-- 1. 用户表
-- ============================================
CREATE TABLE IF NOT EXISTS users (
    id          CHAR(36) PRIMARY KEY,              -- UUID
    username    VARCHAR(64) NOT NULL UNIQUE,
    password_hash VARCHAR(256) NOT NULL,
    nickname    VARCHAR(128) DEFAULT NULL,
    avatar      VARCHAR(512) DEFAULT NULL,
    preferences JSON DEFAULT NULL,                 -- {"default_model": "qwen", "language": "zh"}
    status      TINYINT NOT NULL DEFAULT 1,        -- 1=active 0=disabled
    created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_username (username)
) ENGINE=InnoDB;

-- 插入单用户模式的默认用户 (密码: admin123, bcrypt hash)
INSERT INTO users (id, username, password_hash, nickname)
VALUES (
    UUID(),
    'admin',
    '$2b$12$gM.kzdfuhxdL7D6WvYDNq.jn89C1JPfulaUrmvoAN9..XEkZ5n092',
    '管理员'
) ON DUPLICATE KEY UPDATE username=username;

-- ============================================
-- 2. 会话表
-- ============================================
CREATE TABLE IF NOT EXISTS sessions (
    id          CHAR(36) PRIMARY KEY,
    user_id     CHAR(36) NOT NULL,
    title       VARCHAR(256) NOT NULL DEFAULT '新对话',
    mode        VARCHAR(16) NOT NULL DEFAULT 'normal',  -- normal / rag
    status      VARCHAR(16) NOT NULL DEFAULT 'active',   -- active / archived
    created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_user_id (user_id),
    INDEX idx_status (status),
    INDEX idx_updated (updated_at DESC)
) ENGINE=InnoDB;

-- ============================================
-- 3. 消息表
-- ============================================
CREATE TABLE IF NOT EXISTS messages (
    id          CHAR(36) PRIMARY KEY,
    session_id  CHAR(36) NOT NULL,
    role        VARCHAR(16) NOT NULL,                    -- user / assistant / system / tool
    content     TEXT NOT NULL,
    metadata    JSON DEFAULT NULL,                       -- {"sources": [...], "token_count": 450}
    created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_session_id (session_id),
    INDEX idx_created (session_id, created_at)
) ENGINE=InnoDB;

-- ============================================
-- 4. 知识库文档表
-- ============================================
CREATE TABLE IF NOT EXISTS knowledge_docs (
    id          CHAR(36) PRIMARY KEY,
    user_id     CHAR(36) NOT NULL,
    filename    VARCHAR(512) NOT NULL,
    file_type   VARCHAR(32) NOT NULL,                    -- pdf / docx / xlsx / txt / md / image
    file_size   INT NOT NULL DEFAULT 0,
    file_path   VARCHAR(1024) DEFAULT NULL,
    status      VARCHAR(16) NOT NULL DEFAULT 'uploading', -- uploading/parsing/chunking/embedding/done/failed
    chunk_count INT NOT NULL DEFAULT 0,
    char_count  INT NOT NULL DEFAULT 0,                   -- 原文总字符数
    summary     TEXT DEFAULT NULL,                         -- AI 自动生成的文档摘要
    category    VARCHAR(128) DEFAULT NULL,
    error_msg   TEXT DEFAULT NULL,                        -- 失败时的错误信息
    created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_user_id (user_id),
    INDEX idx_status (status),
    INDEX idx_category (category)
) ENGINE=InnoDB;

-- ============================================
-- 4.1 文档分块表 (chunk 去重)
-- ============================================
CREATE TABLE IF NOT EXISTS doc_chunks (
    id           CHAR(36) PRIMARY KEY,
    doc_id       CHAR(36) NOT NULL,
    chunk_index  INT NOT NULL,
    content      TEXT NOT NULL,
    content_hash CHAR(64) NOT NULL,                      -- SHA256 hash, 用于去重
    char_count   INT NOT NULL DEFAULT 0,
    chunk_metadata JSON DEFAULT NULL,                    -- 来源页码/标题等
    created_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_content_hash (content_hash),
    INDEX idx_doc_id (doc_id),
    INDEX idx_doc_chunk (doc_id, chunk_index)
) ENGINE=InnoDB;

-- ============================================
-- 5. 工具表
-- ============================================
CREATE TABLE IF NOT EXISTS tools (
    id                CHAR(36) PRIMARY KEY,
    name              VARCHAR(128) NOT NULL UNIQUE,
    description       TEXT DEFAULT NULL,
    tool_type         VARCHAR(16) NOT NULL DEFAULT 'builtin',  -- builtin / mcp
    parameters_schema JSON DEFAULT NULL,                        -- JSON Schema
    enabled           TINYINT NOT NULL DEFAULT 1,
    created_at        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- ============================================
-- 6. 技能表
-- ============================================
CREATE TABLE IF NOT EXISTS skills (
    id          CHAR(36) PRIMARY KEY,
    name        VARCHAR(128) NOT NULL UNIQUE,
    description TEXT DEFAULT NULL,
    entry_point VARCHAR(256) NOT NULL,
    enabled     TINYINT NOT NULL DEFAULT 1,
    created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- ============================================
-- 7. MCP Server 表
-- ============================================
CREATE TABLE IF NOT EXISTS mcp_servers (
    id          CHAR(36) PRIMARY KEY,
    name        VARCHAR(128) NOT NULL UNIQUE,
    transport   VARCHAR(16) NOT NULL,                     -- stdio / sse
    command     VARCHAR(512) DEFAULT NULL,
    args        JSON DEFAULT NULL,
    env         JSON DEFAULT NULL,
    url         VARCHAR(512) DEFAULT NULL,
    status      VARCHAR(16) NOT NULL DEFAULT 'disconnected', -- connected / disconnected / error
    created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- ============================================
-- 8. 任务执行记录表
-- ============================================
CREATE TABLE IF NOT EXISTS task_executions (
    id              CHAR(36) PRIMARY KEY,
    session_id      CHAR(36) NOT NULL,
    user_task       TEXT NOT NULL,
    plan            JSON DEFAULT NULL,
    execution_results JSON DEFAULT NULL,
    status          VARCHAR(16) NOT NULL DEFAULT 'planning', -- planning/executing/reflecting/done/failed
    retry_count     INT NOT NULL DEFAULT 0,
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at     DATETIME DEFAULT NULL,
    INDEX idx_session_id (session_id),
    INDEX idx_status (status)
) ENGINE=InnoDB;
