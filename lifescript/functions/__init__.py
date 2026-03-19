"""関数ライブラリ — DSLから呼べる関数群。

関数ライブラリの拡充 = LifeScriptのロードマップそのもの。
"""

from .notify import notify
from .calendar import calendar_add, calendar_read, calendar_suggest
from .web import web_fetch
from .widget import widget_show
from .gmail import gmail_unread, gmail_search, gmail_summarize, gmail_send
from .machine import machine_analyze, machine_suggest
from .device import device_cpu, device_memory, device_info
from .weather import weather_get
from .time_fn import time_now
from .random_fn import random_pick, random_number
from .streak import streak_count, streak_update
from .memory import memory_read, memory_write
from .math_fn import math_calc, math_round
from .date_fn import date_diff
from .list_fn import list_join, list_count
from .translate_fn import translate
from .summarize_fn import summarize
from .qr_fn import qr_generate
from .sound_fn import sound_play

# DSL内で使える関数名 → 実際のPython関数のマッピング
FUNCTION_MAP: dict[str, callable] = {
    "notify": notify,
    "calendar_add": calendar_add,
    "calendar_read": calendar_read,
    "calendar_suggest": calendar_suggest,
    "web_fetch": web_fetch,
    "widget_show": widget_show,
    "gmail_unread": gmail_unread,
    "gmail_search": gmail_search,
    "gmail_summarize": gmail_summarize,
    "gmail_send": gmail_send,
    "machine_analyze": machine_analyze,
    "machine_suggest": machine_suggest,
    "device_cpu": device_cpu,
    "device_memory": device_memory,
    "device_info": device_info,
    "weather_get": weather_get,
    "time_now": time_now,
    "random_pick": random_pick,
    "random_number": random_number,
    "streak_count": streak_count,
    "streak_update": streak_update,
    "memory_read": memory_read,
    "memory_write": memory_write,
    "math_calc": math_calc,
    "math_round": math_round,
    "date_diff": date_diff,
    "list_join": list_join,
    "list_count": list_count,
    "translate": translate,
    "summarize": summarize,
    "qr_generate": qr_generate,
    "sound_play": sound_play,
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
    {
        "name": "web_fetch",
        "signature": 'web_fetch(url: str, summary: bool = True) -> str',
        "description": "URLの内容を取得しLLMで要約して返す。summary=Falseで生テキスト。widget_showと組み合わせてホーム画面に表示できる。",
    },
    {
        "name": "widget_show",
        "signature": 'widget_show(name: str, content: str, icon: str = "article")',
        "description": "ホーム画面にカスタムウィジェットを表示/更新する。nameがウィジェットのタイトルになる。スクリプトが実行されるたびに内容が最新化される。",
    },
    {
        "name": "gmail_unread",
        "signature": "gmail_unread(limit: int = 10) -> list[dict]",
        "description": "未読メールを取得。各要素は {subject, from, date, snippet, body} を持つdict。Google認証が必要。",
    },
    {
        "name": "gmail_search",
        "signature": "gmail_search(query: str, limit: int = 10) -> list[dict]",
        "description": 'Gmailを検索。query はGmail検索構文（例: "from:amazon.co.jp", "subject:請求書", "newer_than:1d"）。Google認証が必要。',
    },
    {
        "name": "gmail_summarize",
        "signature": "gmail_summarize(limit: int = 5) -> str",
        "description": "未読メールをLLMで要約して返す。重要度順に整理される。widget_showと組み合わせてホーム画面に表示可能。Google認証が必要。",
    },
    {
        "name": "gmail_send",
        "signature": 'gmail_send(to: str, subject: str, body: str) -> str',
        "description": "メールを送信する。Google認証が必要。",
    },
    {
        "name": "machine_analyze",
        "signature": "machine_analyze() -> list[dict]",
        "description": "コンテキスト分析を実行。カレンダー・メール・traitsを分析し、提案をmachine_logsに自動生成する。戻り値は生成された提案のリスト。",
    },
    {
        "name": "machine_suggest",
        "signature": 'machine_suggest(message: str, reason: str = "")',
        "description": "ダリーの提案をmachine_logsに直接書き込む。ホーム画面の提案セクションに通知として表示される。reasonで理由を付与できる。",
    },
    {
        "name": "device_cpu",
        "signature": "device_cpu() -> float",
        "description": "PCのCPU使用率(%)を返す。",
    },
    {
        "name": "device_memory",
        "signature": "device_memory() -> dict",
        "description": "PCのメモリ情報を返す。{total_gb, used_gb, percent}。",
    },
    {
        "name": "device_info",
        "signature": "device_info() -> dict",
        "description": "デバイスの基本情報を返す。{os, os_version, machine, python, cpu_count}。",
    },
    {
        "name": "weather_get",
        "signature": "weather_get(location: str | None = None) -> dict",
        "description": '天気を取得。{condition, description, temp, feels_like, humidity, wind_speed, location}を返す。conditionは"rain","clear","clouds"等。',
    },
    {
        "name": "time_now",
        "signature": "time_now() -> dict",
        "description": "現在の日時情報を返す。{hour, minute, weekday, weekday_ja, date, time, is_morning, is_afternoon, is_evening, is_weekend, is_weekday}。",
    },
    {
        "name": "random_pick",
        "signature": "random_pick(items: list) -> object",
        "description": "リストからランダムに1つ選んで返す。",
    },
    {
        "name": "random_number",
        "signature": "random_number(low: int = 0, high: int = 100) -> int",
        "description": "low以上high以下のランダムな整数を返す。",
    },
    {
        "name": "streak_count",
        "signature": "streak_count(habit_name: str) -> int",
        "description": "指定した習慣の継続日数を返す。未登録なら0。",
    },
    {
        "name": "streak_update",
        "signature": "streak_update(habit_name: str, done: bool = True) -> int",
        "description": "習慣の完了状況を記録。done=Trueでストリーク+1、Falseでリセット。更新後のカウントを返す。",
    },
    {
        "name": "memory_read",
        "signature": "memory_read(key: str, default: object = None) -> object",
        "description": "DSLメモリからkeyの値を読み出す。存在しなければdefaultを返す。スクリプト間で状態を共有できる。",
    },
    {
        "name": "memory_write",
        "signature": "memory_write(key: str, value: object) -> None",
        "description": "DSLメモリにkey-valueを保存する。既存のkeyは上書き。スクリプト間で状態を共有できる。",
    },
    {
        "name": "math_calc",
        "signature": "math_calc(expression: str) -> float",
        "description": "数式を安全に評価する。+,-,*,/,**,%に対応。例: math_calc(\"3*4+2\") → 14。",
    },
    {
        "name": "math_round",
        "signature": "math_round(value: float, digits: int = 0) -> float",
        "description": "値を四捨五入する。digitsで小数点以下の桁数を指定。",
    },
    {
        "name": "date_diff",
        "signature": "date_diff(target: str, from_date: str | None = None) -> int",
        "description": "日付間の日数差を計算。targetはYYYY-MM-DD形式。from_date省略で今日（JST）基準。未来なら正、過去なら負。",
    },
    {
        "name": "list_join",
        "signature": 'list_join(items: list, separator: str = ", ") -> str',
        "description": "リストの要素を文字列に結合する。separatorで区切り文字を指定。",
    },
    {
        "name": "list_count",
        "signature": "list_count(items: list, value: object) -> int",
        "description": "リスト内の指定値の出現回数をカウントする。",
    },
    {
        "name": "translate",
        "signature": 'translate(text: str, to_lang: str = "ja") -> str',
        "description": "LLMでテキストを翻訳する。to_langに言語コード（ja,en,zh,ko等）を指定。",
    },
    {
        "name": "summarize",
        "signature": "summarize(text: str, max_lines: int = 3) -> str",
        "description": "LLMでテキストを日本語の箇条書きで要約する。max_linesで行数指定。web_fetchと組み合わせ可能。",
    },
    {
        "name": "qr_generate",
        "signature": "qr_generate(data: str, size: int = 200) -> str",
        "description": "QRコード画像のURLを生成する。dataにURL・テキスト等を指定。machine_logsにも記録される。",
    },
    {
        "name": "sound_play",
        "signature": 'sound_play(sound: str = "default") -> None',
        "description": 'macOSのシステムサウンドを再生。sound: "default"(Ping), "alert"(Basso), "success"(Glass), "error"(Sosumi)。',
    },
]
