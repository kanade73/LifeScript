"""streak.*() — 習慣トラッキング関数。

streak_count(habit_name) で継続日数を取得、
streak_update(habit_name, done) で日次更新する。
"""

from __future__ import annotations

from ..database.client import db_client
from .. import log_queue


def streak_count(habit_name: str) -> int:
    """指定した習慣の継続日数を返す。未登録なら0。

    例: streak_count("運動") → 7
    """
    count = db_client.get_streak(habit_name)
    log_queue.log("streak", f"{habit_name}: {count}日継続中")
    return count


def streak_update(habit_name: str, done: bool = True) -> int:
    """習慣の完了状況を記録する。

    done=True でストリーク +1、done=False でリセット(0)。
    更新後のカウントを返す。

    例: streak_update("運動", True) → 8
    """
    if done:
        current = db_client.get_streak(habit_name)
        new_count = current + 1
        db_client.update_streak(habit_name, new_count)
        log_queue.log("streak", f"{habit_name}: {current} → {new_count}日")
        return new_count
    else:
        db_client.update_streak(habit_name, 0)
        log_queue.log("streak", f"{habit_name}: リセット → 0日")
        return 0
