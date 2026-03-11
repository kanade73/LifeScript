"""ログプラグイン — メッセージをデータベースに書き込む。

LifeScript の主要アクション: log("message") でメッセージを記録し、
PC のログパネルと iPhone ダッシュボードに表示する。
"""

from __future__ import annotations

from .base import Plugin
from ..database.client import db_client
from .. import log_queue


class LogPlugin(Plugin):
    """共有データベースにログエントリを書き込むプラグイン。"""

    _current_rule_id: str | None = None

    @property
    def name(self) -> str:
        return "log"

    def set_current_rule(self, rule_id: str | None) -> None:
        """後続の log() 呼び出しに使うルール ID を設定する。"""
        self._current_rule_id = rule_id

    def log(self, message: str) -> None:
        """ログエントリをデータベースと UI ログキューに書き込む。"""
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
    """内部用: サンドボックス実行前に runner から呼ばれる。"""
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
