"""notify() — 通知関数。

notify(message, at?) でアプリ内通知を送る。
at を省略した場合は即時実行。
"""

from __future__ import annotations

from ..database.client import db_client
from .. import log_queue


def notify(message: str, at: str | None = None) -> None:
    """指定時刻（または即時）に通知を送る。"""
    if at:
        db_client.add_machine_log(
            action_type="notify_scheduled",
            content=f"[予約通知 at={at}] {message}",
        )
        log_queue.log("notify", f"予約通知を登録: {message} (at={at})")
    else:
        db_client.add_machine_log(
            action_type="notify",
            content=message,
        )
        log_queue.log("notify", f"通知: {message}")
