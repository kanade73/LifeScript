"""calendar.*() — カレンダー関数群。

calendar_add / calendar_read / calendar_suggest の実装。
Supabase の calendar_events テーブルを操作する。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from ..database.client import db_client
from .. import log_queue


def _week_range() -> tuple[str, str]:
    now = datetime.now(timezone(timedelta(hours=9)))
    start = now - timedelta(days=now.weekday())
    start = start.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=7)
    return start.isoformat(), end.isoformat()


def _today_range() -> tuple[str, str]:
    now = datetime.now(timezone(timedelta(hours=9)))
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    return start.isoformat(), end.isoformat()


def _month_range() -> tuple[str, str]:
    now = datetime.now(timezone(timedelta(hours=9)))
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if now.month == 12:
        end = start.replace(year=now.year + 1, month=1)
    else:
        end = start.replace(month=now.month + 1)
    return start.isoformat(), end.isoformat()


def calendar_add(
    title: str,
    start: str,
    end: str | None = None,
    note: str = "",
) -> dict:
    """カレンダーにイベントを追加する。"""
    existing = db_client.get_events(start_from=start, start_to=start)
    for event in existing:
        if event.get("start_at") == start and event.get("source") == "machine":
            log_queue.log(
                "calendar",
                f"同時刻イベントをスキップ: {title} ({start}) / existing={event.get('title', '')}",
            )
            return event

    event = db_client.add_event(
        title=title,
        start_at=start,
        end_at=end,
        note=note,
        source="machine",
    )
    log_queue.log("calendar", f"イベント追加: {title} ({start})")
    return event


def calendar_read(
    keyword: str | None = None,
    range: str = "this_week",
) -> list[dict]:
    """カレンダーからイベントを取得する。

    返り値のリストには count_this_week 属性をシミュレートするため、
    各イベントの辞書に加え、リスト自体に情報を付与。
    """
    range_map = {
        "this_week": _week_range,
        "today": _today_range,
        "this_month": _month_range,
    }
    range_fn = range_map.get(range, _week_range)
    start_from, start_to = range_fn()

    events = db_client.get_events(
        keyword=keyword,
        start_from=start_from,
        start_to=start_to,
    )

    # count_this_week を付与するため、今週のイベントも取得
    if keyword:
        ws, we = _week_range()
        week_events = db_client.get_events(keyword=keyword, start_from=ws, start_to=we)
        count_this_week = len(week_events)
    else:
        count_this_week = len(events) if range == "this_week" else 0

    # リストにカスタム属性を付与（DSL内で .count_this_week として参照可能）
    class EventList(list):
        pass

    result = EventList(events)
    result.count_this_week = count_this_week  # type: ignore[attr-defined]
    return result


def calendar_suggest(
    title: str,
    on: str,
    note: str = "",
) -> None:
    """イベントの提案をmachine_logsに書き込む。"""
    content = f"提案: 「{title}」を {on} に追加しませんか？"
    if note:
        content += f" ({note})"
    db_client.add_machine_log(
        action_type="calendar_suggest",
        content=content,
    )
    log_queue.log("calendar", f"提案: {title} (on={on})")
