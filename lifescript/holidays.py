"""祝日取得ヘルパー — LLMで月単位に取得し、共有キャッシュする。"""

from __future__ import annotations

import json
import re
from datetime import date
from typing import Any

from . import llm as _llm


_HOLIDAY_CACHE: dict[tuple[int, int, str, str], dict[date, str]] = {}


def clear_cache() -> None:
    _HOLIDAY_CACHE.clear()


def _parse_holiday_response(content: str) -> dict[date, str]:
    text = re.sub(r"```(?:json)?\s*", "", content).strip().rstrip("`").strip()
    data = json.loads(text)
    items = data.get("holidays", [])
    result: dict[date, str] = {}

    if not isinstance(items, list):
        return result

    for item in items:
        if not isinstance(item, dict):
            continue
        date_str = str(item.get("date", "")).strip()
        name = str(item.get("name", "")).strip() or "祝日"
        if not date_str:
            continue
        try:
            d = date.fromisoformat(date_str)
        except ValueError:
            continue
        result[d] = name
    return result


def get_month_holidays(
    year: int,
    month: int,
    *,
    model: str,
    api_base: str | None = None,
) -> dict[date, str]:
    key = (year, month, model, api_base or "")
    if key in _HOLIDAY_CACHE:
        return _HOLIDAY_CACHE[key]

    start = date(year, month, 1)
    next_month = date(year + (1 if month == 12 else 0), 1 if month == 12 else month + 1, 1)
    end = next_month.fromordinal(next_month.toordinal() - 1)

    kwargs: dict[str, Any] = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "あなたは日本の祝日データ抽出器です。"
                    "指定された期間内の日本の祝日をJSONのみで返してください。"
                    "形式は {\"holidays\": [{\"date\": \"YYYY-MM-DD\", \"name\": \"祝日名\"}]}"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"期間: {start.isoformat()} から {end.isoformat()}\n"
                    "日本の祝日のみを返してください。"
                ),
            },
        ],
        "temperature": 0,
    }
    if api_base:
        kwargs["api_base"] = api_base

    response = _llm.completion(**kwargs)
    parsed = _parse_holiday_response(response.choices[0].message.content)
    _HOLIDAY_CACHE[key] = parsed
    return parsed


def get_holiday_dates_between(
    start: date,
    end: date,
    *,
    model: str,
    api_base: str | None = None,
) -> set[date]:
    if end < start:
        return set()

    holidays: set[date] = set()
    year = start.year
    month = start.month

    while (year, month) <= (end.year, end.month):
        month_data = get_month_holidays(year, month, model=model, api_base=api_base)
        for d in month_data.keys():
            if start <= d <= end:
                holidays.add(d)

        if month == 12:
            year += 1
            month = 1
        else:
            month += 1

    return holidays
