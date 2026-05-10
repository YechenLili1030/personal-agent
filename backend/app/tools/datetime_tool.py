"""获取当前日期和时间"""

from datetime import datetime
from langchain_core.tools import tool


@tool
def get_current_date() -> str:
    """获取当前日期和时间，包括星期、农历年份提示。用于需要知道"今天是什么日期"的场景。"""
    now = datetime.now()
    weekdays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    return (
        f"当前日期: {now.strftime('%Y年%m月%d日')} {weekdays[now.weekday()]}\n"
        f"当前时间: {now.strftime('%H:%M:%S')}"
    )
