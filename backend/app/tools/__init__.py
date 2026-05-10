"""内置工具集"""

from .weather import get_weather
from .datetime_tool import get_current_date

ALL_TOOLS = [get_weather, get_current_date]
