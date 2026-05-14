"""MCP 客户端管理器 — 连接外部 MCP Server，获取工具供 LLM 调用"""

from __future__ import annotations
import logging
from langchain_mcp_adapters.client import MultiServerMCPClient
from ..core.config import BAIDU_MAP_API_KEY

logger = logging.getLogger(__name__)

_client: MultiServerMCPClient | None = None
_mcp_tools: list = []


def build_mcp_servers_config() -> dict:
    """根据环境变量构建 MCP 服务器配置"""
    servers = {}

    if BAIDU_MAP_API_KEY:
        servers["baidu-map"] = {
            "transport": "stdio",
            "command": "npx",
            "args": ["-y", "@baidumap/mcp-server-baidu-map"],
            "env": {"BAIDU_MAP_API_KEY": BAIDU_MAP_API_KEY},
        }
        logger.info("已配置 MCP Server: baidu-map")
    else:
        logger.debug("BAIDU_MAP_API_KEY 未设置，跳过 baidu-map MCP Server")

    return servers


async def init_mcp_client():
    """启动时初始化 MCP 客户端，连接所有配置的 MCP Server"""
    global _client, _mcp_tools

    config = build_mcp_servers_config()
    if not config:
        logger.info("无 MCP Server 配置，跳过 MCP 客户端初始化")
        return

    try:
        _client = MultiServerMCPClient(config)
        # 先不获取工具列表，等到首次使用时再加载（部分 server 启动慢）
        logger.info("MCP 客户端已创建，servers=%s", list(config.keys()))
    except Exception as e:
        logger.warning("MCP 客户端创建失败: %s", e)


async def get_mcp_tools(cache: bool = True) -> list:
    """获取所有 MCP Server 暴露的 LangChain 工具"""
    global _client, _mcp_tools

    if cache and _mcp_tools:
        return _mcp_tools

    if _client is None:
        return []

    try:
        _mcp_tools = await _client.get_tools()
        logger.info("MCP 工具加载完成: %d 个工具", len(_mcp_tools))
        for t in _mcp_tools:
            logger.debug("  MCP tool: %s", t.name)
        return _mcp_tools
    except Exception as e:
        logger.warning("MCP 工具加载失败: %s", e)
        return []
