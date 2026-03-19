"""memory.*() — DSLメモリ関数。

スクリプト間で状態を共有するための永続メモリ。
machine_logs テーブルを使用して key-value を保存する。
"""

from __future__ import annotations

import json

from ..database.client import db_client
from .. import log_queue

_ACTION_TYPE = "dsl_memory"


def memory_write(key: str, value: object) -> None:
    """メモリにkey-valueを保存する。既存のkeyは上書き。

    例: memory_write("last_weather", "rain")
        memory_write("exercise_count", 5)
    """
    # 既存エントリを検索して削除（上書き）
    logs = db_client.get_machine_logs(limit=200)
    for log in logs:
        if log.get("action_type") == _ACTION_TYPE:
            try:
                data = json.loads(log.get("content", "{}"))
                if data.get("key") == key:
                    db_client.delete_machine_log(log["id"])
                    break
            except (json.JSONDecodeError, KeyError):
                continue

    content = json.dumps({"key": key, "value": value}, ensure_ascii=False)
    db_client.add_machine_log(action_type=_ACTION_TYPE, content=content)
    log_queue.log("memory", f"保存: {key} = {value}")


def memory_read(key: str, default: object = None) -> object:
    """メモリからkeyの値を読み出す。存在しなければdefaultを返す。

    例: memory_read("last_weather") → "rain"
        memory_read("exercise_count", 0) → 5
    """
    logs = db_client.get_machine_logs(limit=200)
    for log in logs:
        if log.get("action_type") == _ACTION_TYPE:
            try:
                data = json.loads(log.get("content", "{}"))
                if data.get("key") == key:
                    value = data.get("value", default)
                    log_queue.log("memory", f"読取: {key} = {value}")
                    return value
            except (json.JSONDecodeError, KeyError):
                continue

    log_queue.log("memory", f"読取: {key} = {default} (未登録)")
    return default
