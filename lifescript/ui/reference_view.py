"""リファレンス画面 — LifeScript 公式ドキュメント。

DSL の書き方・関数ライブラリ・トリガー仕様・サンプルコードを
アプリ内で確認できる。
"""

from __future__ import annotations

import flet as ft

from .app import (
    BG, BLUE, CARD_BG, DARK_TEXT, EDITOR_BG, EDITOR_FG,
    GREEN, LIGHT_TEXT, MID_TEXT, ORANGE, PURPLE, YELLOW, CORAL,
)

_BORDER = "#E8E4DC"


class ReferenceView:
    def __init__(self, page: ft.Page) -> None:
        self._page = page

    def build(self) -> ft.Control:
        return ft.Column([
            ft.Text("Reference", size=22, weight=ft.FontWeight.W_700, color=DARK_TEXT),
            ft.Container(height=4),
            ft.Text("LifeScript DSL 公式リファレンス", size=14, color=MID_TEXT),
            ft.Container(height=12),
            ft.Container(
                content=ft.Column([
                    self._section_overview(),
                    self._section_triggers(),
                    self._section_functions(),
                    self._section_examples(),
                    self._section_tips(),
                ], spacing=16, scroll=ft.ScrollMode.AUTO),
                expand=True,
            ),
        ], expand=True, spacing=0)

    # ==================================================================
    # セクション: 概要
    # ==================================================================
    def _section_overview(self) -> ft.Container:
        return self._card(
            icon=ft.Icons.INFO_ROUNDED,
            icon_color=BLUE,
            title="LifeScript とは",
            children=[
                self._para(
                    "LifeScript は「ダリー」という相棒に自分の生活文脈を伝えるための DSL です。"
                    "ユーザーが書いたルールは LLM によって Python にコンパイルされ、"
                    "スケジューラが自動的に実行します。"
                ),
                self._para(
                    "書けば書くほどダリーが賢くなる — "
                    "関数ライブラリの拡充がそのままプロダクトのロードマップです。"
                ),
                self._label("基本構造"),
                self._code(
                    "# トリガー指定 + アクション\n"
                    "every day:\n"
                    '  notify("今日も頑張ろう！")\n'
                    "\n"
                    "# 条件付きアクション\n"
                    'when calendar.read("バイト").count_this_week >= 4:\n'
                    '  calendar.suggest("回復タイム", on="next_free_morning")'
                ),
            ],
        )

    # ==================================================================
    # セクション: トリガー
    # ==================================================================
    def _section_triggers(self) -> ft.Container:
        return self._card(
            icon=ft.Icons.SCHEDULE_ROUNDED,
            icon_color=ORANGE,
            title="トリガー（実行タイミング）",
            children=[
                self._para("DSL の先頭行でスクリプトの実行タイミングを指定します。"),
                self._table([
                    ("DSL 記法", "動作", "例"),
                    ("every day:", "1日1回（24時間ごと）", 'every day:\\n  notify("おはよう")'),
                    ("every Nh:", "N時間ごとに実行", 'every 2h:\\n  notify("水を飲もう")'),
                    ("every Nm:", "N分ごとに実行", "every 30m:\\n  # 30分ごと"),
                    ("when HH:MM:", "毎日その時刻に実行", 'when 08:00:\\n  notify("朝だよ")'),
                    ("when morning:", "毎日 8:00 に実行", 'when morning:\\n  notify("おはよう")'),
                    ("when evening:", "毎日 18:00 に実行", 'when evening:\\n  notify("お疲れ様")'),
                    ("(指定なし)", "デフォルト 1時間ごと", 'notify("定期チェック")'),
                ]),
            ],
        )

    # ==================================================================
    # セクション: 関数ライブラリ
    # ==================================================================
    def _section_functions(self) -> ft.Container:
        functions = [
            {
                "name": "notify",
                "signature": "notify(message, at?)",
                "color": GREEN,
                "desc": "通知を送信します。",
                "params": [
                    ("message", "str", "通知メッセージ"),
                    ("at", "str | None", "ISO形式の日時。省略で即時通知"),
                ],
                "examples": [
                    'notify("今日も頑張ろう！")',
                    'notify("会議の準備", at="2026-03-15T14:00:00")',
                ],
            },
            {
                "name": "calendar.add",
                "signature": "calendar_add(title, start, end?, note?)",
                "color": BLUE,
                "desc": "カレンダーにイベントを追加します。ホーム画面のカレンダーに即座に反映されます。",
                "params": [
                    ("title", "str", "イベントのタイトル"),
                    ("start", "str", "開始日時（ISO形式）"),
                    ("end", "str | None", "終了日時（省略可）"),
                    ("note", "str", "メモ（省略可）"),
                ],
                "examples": [
                    'calendar_add("ミーティング", start="2026-03-16T10:00:00")',
                    'calendar_add("旅行", start="2026-04-01", end="2026-04-03", note="沖縄")',
                ],
            },
            {
                "name": "calendar.read",
                "signature": 'calendar_read(keyword?, range?) -> EventList',
                "color": BLUE,
                "desc": "カレンダーからイベントを取得します。条件分岐に使います。",
                "params": [
                    ("keyword", "str | None", "タイトルで絞り込み"),
                    ("range", "str", '"this_week" / "today" / "this_month"（デフォルト: "this_week"）'),
                ],
                "examples": [
                    'calendar_read(keyword="バイト")',
                    'calendar_read(keyword="バイト").count_this_week',
                    'calendar_read(range="today")',
                ],
                "note": "戻り値の EventList は .count_this_week 属性を持ち、今週の該当イベント数を返します。",
            },
            {
                "name": "calendar.suggest",
                "signature": 'calendar_suggest(title, on, note?)',
                "color": PURPLE,
                "desc": "イベントの提案を作成します。ホーム画面の「ダリーの提案」に表示され、"
                        "ユーザーが承認するとカレンダーに追加されます。",
                "params": [
                    ("title", "str", "提案するイベントのタイトル"),
                    ("on", "str", '提案日（"tomorrow", "next_free_morning" 等）'),
                    ("note", "str", "メモ（省略可）"),
                ],
                "examples": [
                    'calendar_suggest("回復タイム", on="next_free_morning")',
                    'calendar_suggest("ストレッチ", on="tomorrow", note="15分")',
                ],
            },
            {
                "name": "gmail.unread",
                "signature": "gmail_unread(limit?) -> list[dict]",
                "color": "#EA4335",
                "desc": "未読メールを取得します。各メールは subject, from, date, snippet, body を持ちます。"
                        "Google認証が必要です（設定画面から連携）。",
                "params": [
                    ("limit", "int", "最大取得件数（デフォルト: 10, 最大: 20）"),
                ],
                "examples": [
                    'emails = gmail_unread()',
                    'emails = gmail_unread(limit=5)',
                ],
            },
            {
                "name": "gmail.search",
                "signature": "gmail_search(query, limit?) -> list[dict]",
                "color": "#EA4335",
                "desc": "Gmailを検索します。Gmail検索構文が使えます。Google認証が必要です。",
                "params": [
                    ("query", "str", 'Gmail検索クエリ（例: "from:amazon.co.jp", "subject:請求書"）'),
                    ("limit", "int", "最大取得件数（デフォルト: 10）"),
                ],
                "examples": [
                    'gmail_search("from:amazon.co.jp")',
                    'gmail_search("subject:シフト newer_than:7d")',
                ],
            },
            {
                "name": "gmail.summarize",
                "signature": "gmail_summarize(limit?) -> str",
                "color": "#EA4335",
                "desc": "未読メールをLLMで要約して返します。widget_showと組み合わせてホーム画面に表示できます。Google認証が必要です。",
                "params": [
                    ("limit", "int", "要約対象の最大件数（デフォルト: 5）"),
                ],
                "examples": [
                    'summary = gmail_summarize()',
                    'widget_show("メール要約", gmail_summarize(), icon="mail")',
                ],
            },
            {
                "name": "gmail.send",
                "signature": "gmail_send(to, subject, body) -> str",
                "color": "#EA4335",
                "desc": "メールを送信します。Google認証が必要です。",
                "params": [
                    ("to", "str", "宛先メールアドレス"),
                    ("subject", "str", "件名"),
                    ("body", "str", "本文"),
                ],
                "examples": [
                    'gmail_send("friend@example.com", "今日の予定", "10時に集合です")',
                ],
            },
        ]

        func_cards = []
        for f in functions:
            params_rows = []
            for pname, ptype, pdesc in f["params"]:
                params_rows.append(
                    ft.Container(
                        content=ft.Row([
                            ft.Container(
                                content=ft.Text(pname, size=13, color=DARK_TEXT,
                                                font_family="Courier New", weight=ft.FontWeight.W_600),
                                width=100,
                            ),
                            ft.Container(
                                content=ft.Text(ptype, size=12, color=PURPLE, font_family="Courier New"),
                                width=120,
                            ),
                            ft.Text(pdesc, size=13, color=MID_TEXT, expand=True),
                        ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                        padding=ft.padding.symmetric(vertical=3),
                    )
                )

            examples_code = "\n".join(f["examples"])

            children: list[ft.Control] = [
                ft.Text(f["desc"], size=14, color=DARK_TEXT),
                ft.Container(height=4),
                self._label("パラメータ"),
                *params_rows,
            ]

            if f.get("note"):
                children.append(ft.Container(height=4))
                children.append(ft.Container(
                    content=ft.Row([
                        ft.Icon(ft.Icons.INFO_OUTLINE_ROUNDED, size=14, color=BLUE),
                        ft.Text(f["note"], size=12, color=MID_TEXT, expand=True),
                    ], spacing=6),
                    bgcolor=f"{BLUE}0A",
                    border_radius=8,
                    padding=ft.padding.symmetric(horizontal=10, vertical=8),
                ))

            children.append(ft.Container(height=4))
            children.append(self._label("使用例"))
            children.append(self._code(examples_code))

            func_cards.append(self._func_card(
                name=f["name"],
                signature=f["signature"],
                color=f["color"],
                children=children,
            ))

        return self._card(
            icon=ft.Icons.FUNCTIONS_ROUNDED,
            icon_color=GREEN,
            title="関数ライブラリ",
            children=func_cards,
        )

    # ==================================================================
    # セクション: サンプル
    # ==================================================================
    def _section_examples(self) -> ft.Container:
        return self._card(
            icon=ft.Icons.DESCRIPTION_ROUNDED,
            icon_color=YELLOW,
            title="サンプルコード集",
            children=[
                self._example_block(
                    "毎朝のリマインド",
                    'when 08:00:\n  notify("今日も頑張ろう！")',
                    "毎日 8:00 に通知を送ります。",
                ),
                self._example_block(
                    "バイト過多の検出 & 提案",
                    'when calendar.read("バイト").count_this_week >= 4:\n'
                    '  calendar.suggest("回復タイム", on="next_free_morning")',
                    "今週のバイトが4回以上なら、次の空き時間に回復タイムを提案します。",
                ),
                self._example_block(
                    "定期的な水分補給リマインド",
                    'every 2h:\n  notify("水を飲もう！")',
                    "2時間ごとに水分補給のリマインド。",
                ),
                self._example_block(
                    "イベントの自動登録",
                    'when morning:\n'
                    '  calendar_add("朝のルーティン", start="2026-03-16T07:00:00", note="ストレッチ+瞑想")',
                    "毎朝、朝のルーティンをカレンダーに自動追加します。",
                ),
                self._example_block(
                    "条件付き通知",
                    'when calendar.read(range="today") == []:\n'
                    '  notify("今日は予定がありません。自由に過ごしましょう！")',
                    "今日の予定がゼロなら通知を送ります。",
                ),
            ],
        )

    # ==================================================================
    # セクション: Tips
    # ==================================================================
    def _section_tips(self) -> ft.Container:
        return self._card(
            icon=ft.Icons.TIPS_AND_UPDATES_ROUNDED,
            icon_color=CORAL,
            title="Tips",
            children=[
                self._tip("自然言語でも書ける",
                          "「バイトが週4以上なら回復を提案して」のように書いても、LLM が Python に変換します。"),
                self._tip("関数名は DSL 記法と Python 記法がある",
                          "DSL では calendar.add() と書きますが、コンパイル後の Python では calendar_add() になります。"
                          "どちらで書いても LLM が正しく変換します。"),
                self._tip("トリガーはスクリプト単位",
                          "1つのスクリプトに1つのトリガーが設定されます。"
                          "異なるタイミングで実行したい場合は、別々のスクリプトに分けてください。"),
                self._tip("コンパイル時のみ LLM を使用",
                          "LLM はコンパイル（DSL→Python変換）時のみ呼ばれます。"
                          "実行時は Python コードを直接実行するため、API コストは最小限です。"),
                self._tip("サンドボックス実行",
                          "生成された Python は RestrictedPython でサンドボックス内実行されます。"
                          "import やファイルアクセスは禁止されています。"),
            ],
        )

    # ==================================================================
    # UI ヘルパー
    # ==================================================================
    def _card(self, icon: str, icon_color: str, title: str,
              children: list[ft.Control]) -> ft.Container:
        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Container(
                        content=ft.Icon(icon, size=20, color=CARD_BG),
                        width=36, height=36, bgcolor=icon_color,
                        border_radius=10, alignment=ft.Alignment(0, 0),
                    ),
                    ft.Text(title, size=18, weight=ft.FontWeight.W_700, color=DARK_TEXT),
                ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Divider(height=1, color=_BORDER),
                *children,
            ], spacing=10),
            bgcolor=CARD_BG,
            border_radius=16,
            padding=20,
            border=ft.border.all(1, _BORDER),
        )

    def _func_card(self, name: str, signature: str, color: str,
                   children: list[ft.Control]) -> ft.Container:
        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Container(
                        content=ft.Text(name, size=14, color=CARD_BG, weight=ft.FontWeight.W_700),
                        bgcolor=color,
                        border_radius=8,
                        padding=ft.padding.symmetric(horizontal=10, vertical=4),
                    ),
                    ft.Text(signature, size=13, color=MID_TEXT, font_family="Courier New"),
                ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                *children,
            ], spacing=6),
            bgcolor=BG,
            border_radius=12,
            padding=14,
            border=ft.border.all(1, _BORDER),
        )

    @staticmethod
    def _para(text: str) -> ft.Text:
        return ft.Text(text, size=14, color=DARK_TEXT)

    @staticmethod
    def _label(text: str) -> ft.Text:
        return ft.Text(text, size=13, weight=ft.FontWeight.W_700, color=MID_TEXT)

    @staticmethod
    def _code(text: str) -> ft.Container:
        return ft.Container(
            content=ft.Text(
                text, size=13, color=EDITOR_FG,
                font_family="Courier New", selectable=True,
            ),
            bgcolor=EDITOR_BG,
            border_radius=10,
            padding=ft.padding.symmetric(horizontal=14, vertical=10),
        )

    def _example_block(self, title: str, code: str, desc: str) -> ft.Container:
        return ft.Container(
            content=ft.Column([
                ft.Text(title, size=14, weight=ft.FontWeight.W_600, color=DARK_TEXT),
                self._code(code),
                ft.Text(desc, size=13, color=MID_TEXT),
            ], spacing=6),
            bgcolor=BG,
            border_radius=12,
            padding=12,
            border=ft.border.all(1, _BORDER),
        )

    @staticmethod
    def _tip(title: str, desc: str) -> ft.Container:
        return ft.Container(
            content=ft.Column([
                ft.Text(title, size=14, weight=ft.FontWeight.W_600, color=DARK_TEXT),
                ft.Text(desc, size=13, color=MID_TEXT),
            ], spacing=4),
            padding=ft.padding.symmetric(vertical=4),
        )

    @staticmethod
    def _table(rows: list[tuple[str, ...]]) -> ft.Container:
        header = rows[0]
        data = rows[1:]

        header_row = ft.Container(
            content=ft.Row([
                ft.Text(h, size=12, weight=ft.FontWeight.W_700, color=MID_TEXT, width=160)
                for h in header
            ], spacing=4),
            padding=ft.padding.symmetric(vertical=6, horizontal=8),
            bgcolor=BG,
            border_radius=ft.border_radius.only(top_left=8, top_right=8),
        )

        data_rows = []
        for row in data:
            data_rows.append(ft.Container(
                content=ft.Row([
                    ft.Container(
                        content=ft.Text(row[0], size=13, color=DARK_TEXT,
                                        font_family="Courier New", weight=ft.FontWeight.W_600),
                        width=160,
                    ),
                    ft.Text(row[1], size=13, color=MID_TEXT, width=160),
                    ft.Container(
                        content=ft.Text(row[2], size=12, color=EDITOR_FG,
                                        font_family="Courier New"),
                        bgcolor=EDITOR_BG, border_radius=6,
                        padding=ft.padding.symmetric(horizontal=8, vertical=4),
                        expand=True,
                    ),
                ], spacing=4, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                padding=ft.padding.symmetric(vertical=4, horizontal=8),
            ))

        return ft.Container(
            content=ft.Column([header_row, *data_rows], spacing=0),
            border=ft.border.all(1, _BORDER),
            border_radius=8,
        )
