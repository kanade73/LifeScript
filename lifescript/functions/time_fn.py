"""time.*() — 時刻関数。

time_now() で現在の日時情報を取得する。
DSL内で条件分岐に使うためのプリミティブ。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

_JST = timezone(timedelta(hours=9))

_WEEKDAY_JA = ["月", "火", "水", "木", "金", "土", "日"]


def time_now() -> dict:
    """現在の日時情報を返す。

    Returns:
        dict: {
            hour: int,          # 時 (0-23)
            minute: int,        # 分 (0-59)
            weekday: int,       # 曜日 (0=月, 6=日)
            weekday_ja: str,    # 曜日の日本語 ("月", "火", ...)
            date: str,          # 日付 "YYYY-MM-DD"
            time: str,          # 時刻 "HH:MM"
            month: int,         # 月 (1-12)
            day: int,           # 日 (1-31)
            is_morning: bool,   # 5:00-11:59
            is_afternoon: bool, # 12:00-17:59
            is_evening: bool,   # 18:00-23:59
            is_night: bool,     # 0:00-4:59
            is_weekday: bool,   # 月-金
            is_weekend: bool,   # 土-日
        }
    """
    now = datetime.now(_JST)
    h = now.hour
    wd = now.weekday()

    return {
        "hour": h,
        "minute": now.minute,
        "weekday": wd,
        "weekday_ja": _WEEKDAY_JA[wd],
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M"),
        "month": now.month,
        "day": now.day,
        "is_morning": 5 <= h < 12,
        "is_afternoon": 12 <= h < 18,
        "is_evening": 18 <= h < 24,
        "is_night": 0 <= h < 5,
        "is_weekday": wd < 5,
        "is_weekend": wd >= 5,
    }
