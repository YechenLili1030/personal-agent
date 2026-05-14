"""MCP (Model Context Protocol) 客户端 — 连接外部工具服务器"""

from .client import init_mcp_client, get_mcp_tools, build_mcp_servers_config

__all__ = ["init_mcp_client", "get_mcp_tools", "build_mcp_servers_config"]
