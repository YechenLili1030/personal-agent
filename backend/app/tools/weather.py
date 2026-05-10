"""Open-Meteo 天气查询工具（免费，无需 API Key）"""

import logging
from datetime import datetime, timedelta
import requests
from langchain_core.tools import tool

logger = logging.getLogger(__name__)

WEATHER_CODES = {
    0: "晴天", 1: "大部晴朗", 2: "多云", 3: "阴天",
    45: "雾", 48: "冻雾",
    51: "小毛毛雨", 53: "毛毛雨", 55: "大毛毛雨",
    61: "小雨", 63: "中雨", 65: "大雨",
    71: "小雪", 73: "中雪", 75: "大雪",
    80: "阵雨", 81: "中阵雨", 82: "大阵雨",
    85: "小阵雪", 86: "大阵雪",
    95: "雷暴", 96: "冰雹雷暴", 99: "强冰雹雷暴",
}


@tool
def get_weather(location: str, date: str = "") -> str:
    """查询指定地区在指定日期的天气情况。

    Args:
        location: 城市名称，如"北京市"、"上海市"、"东京"、"New York"
        date: 日期，格式 YYYY-MM-DD，如"2026-05-15"。不填则默认查询今天。
    """
    try:
        # 1. 地理编码
        geo_url = "https://geocoding-api.open-meteo.com/v1/search"
        geo_resp = requests.get(geo_url, params={
            "name": location, "count": 1, "language": "zh",
        }, timeout=10)
        geo_resp.raise_for_status()
        geo_data = geo_resp.json()

        if not geo_data.get("results"):
            return f"未找到城市「{location}」，请确认城市名称是否正确。"

        city = geo_data["results"][0]
        lat = city["latitude"]
        lon = city["longitude"]
        city_name = city.get("name", location)
        country = city.get("country", "")

        # 2. 确定查询日期
        today = datetime.now().date()
        target_date = today
        if date:
            try:
                target_date = datetime.strptime(date, "%Y-%m-%d").date()
            except ValueError:
                return f"日期格式错误: {date}，请使用 YYYY-MM-DD 格式。"
            if target_date < today:
                return f"无法查询过去的天气 ({date})，Open-Meteo 仅支持今天及未来 7 天的预报。"

        max_forecast = today + timedelta(days=7)
        if target_date > max_forecast:
            return f"Open-Meteo 仅支持未来 7 天预报，最远可查询 {max_forecast.strftime('%Y-%m-%d')}。"

        # 3. 获取天气
        weather_url = "https://api.open-meteo.com/v1/forecast"
        weather_resp = requests.get(weather_url, params={
            "latitude": lat,
            "longitude": lon,
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,weathercode,windspeed_10m_max",
            "timezone": "Asia/Shanghai",
            "start_date": target_date.isoformat(),
            "end_date": target_date.isoformat(),
        }, timeout=10)
        weather_resp.raise_for_status()
        data = weather_resp.json()

        daily = data.get("daily", {})
        if not daily.get("time"):
            return f"暂无 {city_name} 在 {target_date} 的天气数据。"

        idx = 0
        temp_max = daily["temperature_2m_max"][idx]
        temp_min = daily["temperature_2m_min"][idx]
        precip = daily["precipitation_sum"][idx]
        code = daily["weathercode"][idx]
        wind = daily["windspeed_10m_max"][idx]
        weather_desc = WEATHER_CODES.get(code, f"未知({code})")

        return (
            f"「{city_name}」{country} {target_date} 天气\n"
            f"🌤 天气: {weather_desc}\n"
            f"🌡 温度: {temp_min}°C ~ {temp_max}°C\n"
            f"💧 降水量: {precip} mm\n"
            f"💨 最大风速: {wind} km/h"
        )

    except requests.RequestException as e:
        logger.error("天气查询网络错误: %s", e)
        return f"天气查询失败: 网络错误，请稍后重试。"
    except Exception as e:
        logger.exception("天气查询异常")
        return f"天气查询失败: {e}"
