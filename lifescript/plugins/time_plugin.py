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
