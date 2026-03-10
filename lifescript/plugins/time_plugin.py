"""Time plugin - provides current time and date information."""

from datetime import datetime

from .base import Plugin


class TimePlugin(Plugin):
    @property
    def name(self) -> str:
        return "time"

    @property
    def requires_connection(self) -> bool:
        return False

    def fetch_now(self) -> str:
        """Returns current time as 'HH:MM'."""
        return datetime.now().strftime("%H:%M")

    def fetch_today(self) -> dict:
        """Returns today's weekday and date."""
        now = datetime.now()
        return {
            "weekday": now.strftime("%A"),
            "date": now.strftime("%Y-%m-%d"),
        }


_plugin = TimePlugin()


# Functions exposed to the sandbox
def fetch_time_now() -> str:
    return _plugin.fetch_now()


def fetch_time_today() -> dict:
    return _plugin.fetch_today()


# Auto-discovery registration
PLUGIN_EXPORTS = [
    {
        "name": "fetch_time_now",
        "func": fetch_time_now,
        "signature": "fetch_time_now() -> str",
        "description": '現在時刻を "HH:MM" 形式で返す',
    },
    {
        "name": "fetch_time_today",
        "func": fetch_time_today,
        "signature": 'fetch_time_today() -> dict  ({"weekday": "Monday", "date": "2024-01-01"})',
        "description": "今日の曜日と日付を辞書で返す",
    },
]
