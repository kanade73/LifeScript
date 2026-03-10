"""Log plugin - writes messages to the database (Supabase or SQLite).

This is the primary action in LifeScript: log("message") records
a message that appears in the PC log panel and the iPhone dashboard.
"""

from __future__ import annotations

from .base import Plugin
from ..database.client import db_client
from .. import log_queue


class LogPlugin(Plugin):
    """Plugin that writes log entries to the shared database."""

    _current_rule_id: str | None = None

    @property
    def name(self) -> str:
        return "log"

    def set_current_rule(self, rule_id: str | None) -> None:
        """Set the rule context for subsequent log() calls."""
        self._current_rule_id = rule_id

    def log(self, message: str) -> None:
        """Write a log entry to the database and the UI log queue."""
        db_client.save_log(
            rule_id=self._current_rule_id,
            message=str(message),
            result="success",
        )
        log_queue.log("log", str(message))


_plugin = LogPlugin()


def log_message(message: str) -> None:
    _plugin.log(message)


def _set_rule_context(rule_id: str | None) -> None:
    """Internal: called by the sandbox runner before execution."""
    _plugin.set_current_rule(rule_id)


# Auto-discovery registration
PLUGIN_EXPORTS = [
    {
        "name": "log",
        "func": log_message,
        "signature": "log(message: str) -> None",
        "description": "メッセージをログに記録する（Supabase/ダッシュボードに表示）",
    },
]
