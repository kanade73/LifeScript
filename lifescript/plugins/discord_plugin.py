"""Discord Webhook プラグイン — Webhook URL 経由でメッセージを送信する（Bot トークン不要）。"""

from __future__ import annotations

import httpx

from .base import Plugin


class DiscordPlugin(Plugin):
    def __init__(self) -> None:
        self._webhook_url: str | None = None

    @property
    def name(self) -> str:
        return "Discord"

    @property
    def requires_connection(self) -> bool:
        return True

    def set_webhook(self, webhook_url: str) -> None:
        self._webhook_url = webhook_url

    def clear_webhook(self) -> None:
        self._webhook_url = None

    def check_connection(self) -> bool:
        return bool(self._webhook_url)

    def notify(self, message: str) -> None:
        if not self.check_connection():
            from ..exceptions import ServiceNotConnectedError

            raise ServiceNotConnectedError("Discord")

        with httpx.Client(timeout=10.0) as client:
            resp = client.post(self._webhook_url, json={"content": message})
            resp.raise_for_status()


# Singleton
discord_plugin = DiscordPlugin()


def notify_discord(message: str) -> None:
    discord_plugin.notify(message)


# Auto-discovery registration
PLUGIN_EXPORTS = [
    {
        "name": "notify_discord",
        "func": notify_discord,
        "signature": "notify_discord(message: str) -> None",
        "description": "Discordチャンネルにメッセージを送信する（Webhook経由）",
    },
]
