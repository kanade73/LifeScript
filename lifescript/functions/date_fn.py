"""date.*() --- 日付関数。

date_diff(target, from_date?) で日付間の日数差を計算する。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .. import log_queue

_JST = timezone(timedelta(hours=9))


def date_diff(target: str, from_date: str | None = None) -> int:
    """日付間の日数差を計算する。

    Args:
        target: 対象日付（YYYY-MM-DD形式）
        from_date: 基準日付（YYYY-MM-DD形式）。Noneの場合は今日（JST）

    Returns:
        日数差（targetが未来なら正、過去なら負）
    """
    try:
        target_date = datetime.strptime(target, "%Y-%m-%d").date()
    except ValueError as e:
        log_queue.log("date", f"日付形式エラー (target): {target}", "ERROR")
        raise ValueError(f"target の日付形式が正しくありません (YYYY-MM-DD): {target}") from e

    if from_date is not None:
        try:
            base_date = datetime.strptime(from_date, "%Y-%m-%d").date()
        except ValueError as e:
            log_queue.log("date", f"日付形式エラー (from_date): {from_date}", "ERROR")
            raise ValueError(f"from_date の日付形式が正しくありません (YYYY-MM-DD): {from_date}") from e
    else:
        base_date = datetime.now(_JST).date()

    diff = (target_date - base_date).days
    log_queue.log("date", f"日付差: {base_date} → {target_date} = {diff}日")
    return diff
