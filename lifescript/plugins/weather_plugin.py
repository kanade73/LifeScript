"""Weather plugin - fetches current weather using wttr.in (no API key required)."""

from __future__ import annotations

import httpx

from .base import Plugin

_WTTR_URL = "https://wttr.in"


class WeatherPlugin(Plugin):
    @property
    def name(self) -> str:
        return "weather"

    @property
    def requires_connection(self) -> bool:
        return False

    def fetch(self, city: str = "Tokyo") -> dict:
        """Fetch current weather for a city."""
        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.get(
                    f"{_WTTR_URL}/{city}",
                    params={"format": "j1"},
                    headers={"Accept-Language": "ja"},
                )
                resp.raise_for_status()
                data = resp.json()
        except Exception as e:
            return {"error": f"天気情報の取得に失敗しました: {e}"}

        current = data.get("current_condition", [{}])[0]
        return {
            "city": city,
            "temp_c": current.get("temp_C", "?"),
            "description": current.get("lang_ja", [{}])[0].get(
                "value", current.get("weatherDesc", [{}])[0].get("value", "?")
            ),
            "humidity": current.get("humidity", "?"),
            "wind_kmph": current.get("windspeedKmph", "?"),
        }


_plugin = WeatherPlugin()


def fetch_weather(city: str = "Tokyo") -> dict:
    return _plugin.fetch(city)


# Auto-discovery registration
PLUGIN_EXPORTS = [
    {
        "name": "fetch_weather",
        "func": fetch_weather,
        "signature": 'fetch_weather(city: str = "Tokyo") -> dict',
        "description": '指定都市の現在の天気を取得する ({"city","temp_c","description","humidity","wind_kmph"})',
    },
]
