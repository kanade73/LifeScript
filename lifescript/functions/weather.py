"""weather.*() — 天気関数。

weather_get(location?) で現在の天気を取得する。
OpenWeatherMap API を使用。
"""

from __future__ import annotations

import os

import httpx

from .. import log_queue

_API_KEY = os.getenv("OPENWEATHER_API_KEY", "")
_BASE_URL = "https://api.openweathermap.org/data/2.5/weather"
_DEFAULT_LOCATION = "Tokyo"


def weather_get(location: str | None = None) -> dict:
    """現在の天気を取得する。

    Returns:
        dict: {
            condition: str,      # "rain", "snow", "clouds", "clear", "thunderstorm", etc.
            description: str,    # 日本語の天気説明 (例: "小雨", "晴天")
            temp: float,         # 気温 (℃)
            feels_like: float,   # 体感温度 (℃)
            humidity: int,       # 湿度 (%)
            wind_speed: float,   # 風速 (m/s)
            location: str,       # 都市名
        }
    """
    api_key = _API_KEY
    if not api_key:
        log_queue.log("weather", "OPENWEATHER_API_KEY が未設定です")
        return _fallback_weather(location or _DEFAULT_LOCATION)

    loc = location or _DEFAULT_LOCATION

    try:
        resp = httpx.get(
            _BASE_URL,
            params={
                "q": loc,
                "appid": api_key,
                "units": "metric",
                "lang": "ja",
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()

        weather_main = data["weather"][0]["main"].lower()
        result = {
            "condition": weather_main,
            "description": data["weather"][0].get("description", ""),
            "temp": round(data["main"]["temp"], 1),
            "feels_like": round(data["main"]["feels_like"], 1),
            "humidity": data["main"]["humidity"],
            "wind_speed": data.get("wind", {}).get("speed", 0),
            "location": data.get("name", loc),
        }
        log_queue.log("weather", f"天気取得: {result['location']} - {result['description']} {result['temp']}℃")
        return result

    except Exception as e:
        log_queue.log("weather", f"天気取得エラー: {e}", "ERROR")
        return _fallback_weather(loc)


def _fallback_weather(location: str) -> dict:
    """API未設定/エラー時のフォールバック。"""
    return {
        "condition": "unknown",
        "description": "取得できませんでした",
        "temp": 0.0,
        "feels_like": 0.0,
        "humidity": 0,
        "wind_speed": 0.0,
        "location": location,
    }
