"""LINE Messaging API プラグイン — プッシュメッセージを送信する。"""

import httpx

from .base import Plugin
from ..exceptions import ServiceNotConnectedError

LINE_PUSH_API = "https://api.line.me/v2/bot/message/push"


class LinePlugin(Plugin):
    def __init__(self) -> None:
        self._channel_token: str | None = None
        self._user_id: str | None = None

    @property
    def name(self) -> str:
        return "LINE"

    @property
    def requires_connection(self) -> bool:
        return True

    def set_credentials(self, channel_token: str, user_id: str) -> None:
        self._channel_token = channel_token
        self._user_id = user_id

    def clear_credentials(self) -> None:
        self._channel_token = None
        self._user_id = None

    def check_connection(self) -> bool:
        return bool(self._channel_token and self._user_id)

    def notify(self, message: str) -> None:
        if not self.check_connection():
            raise ServiceNotConnectedError("LINE")

        headers = {
            "Authorization": f"Bearer {self._channel_token}",
            "Content-Type": "application/json",
        }
        payload = {
            "to": self._user_id,
            "messages": [{"type": "text", "text": message}],
        }
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(LINE_PUSH_API, headers=headers, json=payload)
            resp.raise_for_status()


# Singleton used throughout the app
line_plugin = LinePlugin()


# Function exposed to the sandbox
def notify_line(message: str) -> None:
    line_plugin.notify(message)


# Auto-discovery registration
PLUGIN_EXPORTS = [
    {
        "name": "notify_line",
        "func": notify_line,
        "signature": "notify_line(message: str) -> None",
        "description": "接続済みのLINEユーザーにメッセージを送信する",
    },
]
