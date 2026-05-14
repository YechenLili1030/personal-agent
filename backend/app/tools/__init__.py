"""内置工具集 + MCP 工具合并"""

import logging
from .weather import get_weather
from .datetime_tool import get_current_date

logger = logging.getLogger(__name__)

LOCAL_TOOLS = [get_weather, get_current_date]
ALL_TOOLS: list = list(LOCAL_TOOLS)


async def refresh_all_tools():
    """刷新 ALL_TOOLS：本地工具 + MCP 外部工具（原地修改，保持引用）"""
    from ..mcp.client import get_mcp_tools
    mcp_tools = await get_mcp_tools(cache=True)
    ALL_TOOLS.clear()
    ALL_TOOLS.extend(LOCAL_TOOLS)
    ALL_TOOLS.extend(mcp_tools)
    logger.info("工具列表已刷新: 本地=%d MCP=%d 合计=%d",
                len(LOCAL_TOOLS), len(mcp_tools), len(ALL_TOOLS))
