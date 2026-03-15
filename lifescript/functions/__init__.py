"""関数ライブラリ — DSLから呼べる関数群。

関数ライブラリの拡充 = LifeScriptのロードマップそのもの。
"""

from .notify import notify
from .calendar import calendar_add, calendar_read, calendar_suggest

# DSL内で使える関数名 → 実際のPython関数のマッピング
FUNCTION_MAP: dict[str, callable] = {
    "notify": notify,
    "calendar_add": calendar_add,
    "calendar_read": calendar_read,
    "calendar_suggest": calendar_suggest,
}

# バリデータ用: 許可される関数名の集合
ALLOWED_NAMES: set[str] = set(FUNCTION_MAP.keys())

# コンパイラ用: 関数の説明（システムプロンプトに埋め込む）
FUNCTION_DESCRIPTIONS: list[dict[str, str]] = [
    {
        "name": "notify",
        "signature": "notify(message: str, at: str | None = None)",
        "description": "通知を送る。atにISO形式の日時を指定すると予約通知。省略で即時。",
    },
    {
        "name": "calendar_add",
        "signature": 'calendar_add(title: str, start: str, end: str | None = None, note: str = "")',
        "description": "カレンダーにイベントを追加。startはISO形式の日時文字列。",
    },
    {
        "name": "calendar_read",
        "signature": 'calendar_read(keyword: str | None = None, range: str = "this_week") -> list[dict]',
        "description": 'カレンダーからイベントを取得。keywordでタイトル絞り込み、range="this_week"/"today"/"this_month"で期間指定。',
    },
    {
        "name": "calendar_suggest",
        "signature": 'calendar_suggest(title: str, on: str, note: str = "")',
        "description": "イベントの提案をmachine_logsに記録。ユーザーが承認するとcalendar_addされる。",
    },
]
