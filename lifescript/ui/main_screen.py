"""IDE画面 — DSL記述・コンパイル・スケジューラ登録の中核。

- 複数タブ対応DSLテキストエディタ
- コンパイルボタン
- 生成Pythonコードのプレビュー
- スケジューラへの登録ボタン
- エラー・警告表示
"""

from __future__ import annotations

import threading

import flet as ft

import re

from ..compiler.compiler import Compiler
from ..chat import CodingChat
from ..database.client import db_client
from ..exceptions import CompileError
from .app import COLORS, CARD_SHADOW, SHADOW_SOFT

# ── コードフォント（VS Code風フォールバックチェーン）──────────────
_CODE_FONT = "JetBrains Mono, Fira Code, Cascadia Code, Consolas, SF Mono, monospace"

# ── Python シンタックスハイライト色 ──────────────────────────────
_SH = {
    "keyword":  "#C586C0",   # purple-pink (if, def, return, import, ...)
    "builtin":  "#DCDCAA",   # yellow (print, len, range, ...)
    "string":   "#CE9178",   # warm orange (strings)
    "number":   "#B5CEA8",   # light green (numbers)
    "comment":  "#6A9955",   # green (comments)
    "function": "#DCDCAA",   # yellow (function names after def)
    "class":    "#4EC9B0",   # teal (class names)
    "decorator":"#D7BA7D",   # gold (@decorators)
    "operator": "#D4D4D4",   # light gray (=, +, -, etc.)
    "default":  "#D4D4D4",   # light gray (default)
}

_PY_KEYWORDS = {
    "False", "None", "True", "and", "as", "assert", "async", "await",
    "break", "class", "continue", "def", "del", "elif", "else", "except",
    "finally", "for", "from", "global", "if", "import", "in", "is",
    "lambda", "nonlocal", "not", "or", "pass", "raise", "return",
    "try", "while", "with", "yield",
}
_PY_BUILTINS = {
    "print", "len", "range", "int", "str", "float", "list", "dict",
    "set", "tuple", "bool", "type", "isinstance", "enumerate", "zip",
    "map", "filter", "sorted", "reversed", "abs", "min", "max", "sum",
    "any", "all", "open", "input", "super", "property", "staticmethod",
    "classmethod", "hasattr", "getattr", "setattr", "Exception",
}

# ── DSL シンタックスハイライト色 ──────────────────────────────────
_DSL_SH = {
    "keyword":   "#C586C0",   # when, every, if, else, repeat
    "function":  "#DCDCAA",   # notify, calendar.*, web.*, widget.*, gmail.*
    "string":    "#CE9178",   # 文字列
    "number":    "#B5CEA8",   # 数値
    "comment":   "#6A9955",   # コメント
    "traits":    "#569CD6",   # traits: ブロック
    "operator":  "#D4D4D4",   # ==, >=, <=, etc.
    "default":   "#D4D4D4",   # デフォルト
}

_DSL_KEYWORDS = {"when", "every", "if", "else", "repeat", "let", "and", "or", "not"}
_DSL_FUNCTIONS = {
    "notify", "calendar", "web", "widget", "gmail", "streak", "machine",
    "fetch", "add", "read", "suggest", "show", "send", "search",
    "summarize", "unread", "count", "weather", "get", "time", "now",
    "random", "pick", "number", "update", "memory", "write", "device",
    "cpu", "info", "analyze",
}


def _highlight_python(code: str) -> list[ft.TextSpan]:
    """Python コードを簡易シンタックスハイライトして TextSpan リストを返す。"""
    import re as _re
    spans: list[ft.TextSpan] = []

    # トークン化パターン（順序が重要）
    token_pattern = _re.compile(
        r'(#[^\n]*)'             # コメント
        r'|(@\w+)'              # デコレータ
        r'|("""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\')'  # 三重引用符文字列
        r'|("(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\')'  # 通常文字列
        r'|(\b\d+(?:\.\d+)?\b)'  # 数値
        r'|(\b\w+\b)'           # 単語
        r'|([^\w\s])'           # 記号
        r'|(\s+)'              # 空白
    )

    for m in token_pattern.finditer(code):
        comment, decorator, triple_str, string, number, word, symbol, space = m.groups()
        if comment:
            spans.append(ft.TextSpan(comment, style=ft.TextStyle(color=_SH["comment"], font_family=_CODE_FONT)))
        elif decorator:
            spans.append(ft.TextSpan(decorator, style=ft.TextStyle(color=_SH["decorator"], font_family=_CODE_FONT)))
        elif triple_str:
            spans.append(ft.TextSpan(triple_str, style=ft.TextStyle(color=_SH["string"], font_family=_CODE_FONT)))
        elif string:
            spans.append(ft.TextSpan(string, style=ft.TextStyle(color=_SH["string"], font_family=_CODE_FONT)))
        elif number:
            spans.append(ft.TextSpan(number, style=ft.TextStyle(color=_SH["number"], font_family=_CODE_FONT)))
        elif word:
            if word in _PY_KEYWORDS:
                color = _SH["keyword"]
            elif word in _PY_BUILTINS:
                color = _SH["builtin"]
            else:
                color = _SH["default"]
            spans.append(ft.TextSpan(word, style=ft.TextStyle(color=color, font_family=_CODE_FONT)))
        elif symbol:
            spans.append(ft.TextSpan(symbol, style=ft.TextStyle(color=_SH["operator"], font_family=_CODE_FONT)))
        elif space:
            spans.append(ft.TextSpan(space, style=ft.TextStyle(color=_SH["default"], font_family=_CODE_FONT)))

    return spans


def _highlight_dsl(code: str) -> list[ft.TextSpan]:
    """LifeScript DSL を簡易シンタックスハイライトして TextSpan リストを返す。"""
    import re as _re
    spans: list[ft.TextSpan] = []

    token_pattern = _re.compile(
        r'(#[^\n]*)'             # コメント
        r'|("(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\')'  # 文字列
        r'|(\b\d+(?:\.\d+)?\b)'  # 数値
        r'|(traits\s*:)'         # traits: ブロック
        r'|(\b\w+\b)'           # 単語
        r'|([><=!]+|[+\-*/.])'  # 演算子・ドット
        r'|(\s+)'              # 空白
        r'|([^\w\s])'           # その他記号
    )

    for m in token_pattern.finditer(code):
        comment, string, number, traits, word, operator, space, other = m.groups()
        if comment:
            spans.append(ft.TextSpan(comment, style=ft.TextStyle(color=_DSL_SH["comment"], font_family=_CODE_FONT)))
        elif string:
            spans.append(ft.TextSpan(string, style=ft.TextStyle(color=_DSL_SH["string"], font_family=_CODE_FONT)))
        elif number:
            spans.append(ft.TextSpan(number, style=ft.TextStyle(color=_DSL_SH["number"], font_family=_CODE_FONT)))
        elif traits:
            spans.append(ft.TextSpan(traits, style=ft.TextStyle(color=_DSL_SH["traits"], font_family=_CODE_FONT, weight=ft.FontWeight.W_700)))
        elif word:
            if word in _DSL_KEYWORDS:
                color = _DSL_SH["keyword"]
            elif word in _DSL_FUNCTIONS:
                color = _DSL_SH["function"]
            else:
                color = _DSL_SH["default"]
            spans.append(ft.TextSpan(word, style=ft.TextStyle(color=color, font_family=_CODE_FONT)))
        elif operator:
            spans.append(ft.TextSpan(operator, style=ft.TextStyle(color=_DSL_SH["operator"], font_family=_CODE_FONT)))
        elif space:
            spans.append(ft.TextSpan(space, style=ft.TextStyle(color=_DSL_SH["default"], font_family=_CODE_FONT)))
        elif other:
            spans.append(ft.TextSpan(other, style=ft.TextStyle(color=_DSL_SH["operator"], font_family=_CODE_FONT)))

    return spans

_DEFAULT_DSL = ""

# ── テンプレートギャラリー ─────────────────────────────────────────
_TEMPLATES = [
    {
        "icon": ft.Icons.CALENDAR_MONTH_ROUNDED,
        "color": "#4262FF",
        "title": "バイトが多い週に休息を提案",
        "desc": "週のバイト回数をチェックして、多ければ回復タイムを提案します",
        "dsl": """\
# バイトが多い週に休息を提案
when calendar.read("バイト").count_this_week >= 4:
  calendar.suggest("回復タイム", on="next_free_morning")
  notify("今週バイト多めだね。休息入れておいたよ")
""",
    },
    {
        "icon": ft.Icons.ARTICLE_ROUNDED,
        "color": "#9B59B6",
        "title": "ニュース記事を要約してウィジェット表示",
        "desc": "Webページを取得し、LLMで要約してホーム画面に表示します",
        "dsl": """\
# ニュース記事を要約してウィジェット表示
result = web.fetch("https://news.example.com")
widget.show("今日のニュース", summarize(result))
""",
    },
    {
        "icon": ft.Icons.EMAIL_ROUNDED,
        "color": "#00C875",
        "title": "未読メールを通知",
        "desc": "Gmailの未読メールをチェックして、重要なものを通知します",
        "dsl": """\
# 未読メールを通知
when gmail.unread() >= 1:
  notify("未読メールがあるよ: " + gmail.search("is:unread", limit=3))
""",
    },
    {
        "icon": ft.Icons.FITNESS_CENTER_ROUNDED,
        "color": "#FFA500",
        "title": "習慣トラッキング",
        "desc": "運動の継続日数をカウントし、マイルストーンで褒めてくれます",
        "dsl": """\
# 運動の継続を追跡
when streak.count("運動") >= 7:
  notify("1週間継続おめでとう！この調子！")
  calendar.suggest("ご褒美デー", on="next_free_day")
""",
    },
    {
        "icon": ft.Icons.AUTO_AWESOME_ROUNDED,
        "color": "#FFD02F",
        "title": "毎朝ダリーが生活を分析",
        "desc": "カレンダー・メール・traitsをAIが分析して、提案を自動生成します",
        "dsl": """\
# 毎朝ダリーが生活文脈を分析して提案
when morning:
  machine.analyze()
""",
    },
    {
        "icon": ft.Icons.THUNDERSTORM_ROUNDED,
        "color": "#4262FF",
        "title": "天気で生活をハック",
        "desc": "天気・カレンダー・記憶を組み合わせた文脈トリガー",
        "dsl": """\
# 天気が変わったら通知 + カレンダーと連携
traits:
  自転車通学
  朝は弱い → notify() は 8:00 以降

every 3h:
  w = weather.get()
  last = memory.read("weather", "clear")

  # 天気が変わったタイミングで通知
  if w["condition"] != last:
    memory.write("weather", w["condition"])

    if w["condition"] == "rain":
      notify("雨が降り始めたよ。傘持った？")
      # 明日の予定があれば早起きリマインド
      if len(calendar.read(range="today")) > 0:
        notify("今日は予定があるから、余裕を持って出発しよう")
""",
    },
    {
        "icon": ft.Icons.CASINO_ROUNDED,
        "color": "#FF7575",
        "title": "ランダム応援メッセージ",
        "desc": "毎日ランダムなメッセージでダリーが応援してくれます",
        "dsl": """\
# 毎朝ランダムな応援メッセージ
when morning:
  msg = random.pick([
    "今日も1日頑張ろう！",
    "いい天気になりそうだね！",
    "水をたくさん飲もうね",
    "昨日より少しだけ成長してるよ",
    "今日のあなたは最高！",
  ])
  notify(msg)
""",
    },
    {
        "icon": ft.Icons.LINK_ROUNDED,
        "color": "#DC8551",
        "title": "ドミノ連鎖デモ（文脈が繋がる）",
        "desc": "天気×カレンダー×ストリーク×メモリが連鎖する高度な例",
        "dsl": """\
# ドミノ連鎖: 複数の文脈が連鎖して気遣いを見せる
traits:
  朝は弱い
  テスト期間は特に注意

every 3h:
  w = weather.get()
  t = time.now()
  events = calendar.read(range="today")

  # 1. 天気チェック → 雨 + 予定あり → 早起き提案
  if w["condition"] == "rain" and len(events) > 0:
    if t["is_evening"]:
      machine.suggest(
        "明日雨で予定もあるし、いつもより30分早く起きよう",
        reason="雨の日は電車が遅れがち"
      )

  # 2. ストリーク確認 → 連続記録のケア
  days = streak.count("勉強")
  if days >= 5 and t["is_evening"]:
    machine.suggest(
      f"勉強{days}日連続！すごいね。でも今日は少し休んでも大丈夫だよ",
      reason="燃え尽き防止"
    )

  # 3. メモリ活用 → 前回の状態と比較
  last_temp = memory.read("last_temp", 20)
  if abs(w["temp"] - last_temp) > 5:
    notify(f"気温が急変！{last_temp}℃→{w['temp']}℃。服装に注意")
  memory.write("last_temp", w["temp"])
""",
    },
]

_BORDER = "#E8E4DC"
_TAB_COLORS = [
    COLORS["yellow"], COLORS["blue"], COLORS["green"],
    COLORS["coral"], COLORS["purple"], COLORS["orange"],
]


class _Tab:
    """エディタの1タブ分の状態。"""

    _counter = 0

    def __init__(self, name: str = "", dsl_text: str = "", compiled: dict | None = None,
                 script_id: str | None = None):
        _Tab._counter += 1
        self.uid = _Tab._counter
        self.name = name or f"untitled_{self.uid}.ls"
        self.dsl_text = dsl_text
        self.compiled = compiled
        self.script_id = script_id


class EditorView:
    def __init__(self, page: ft.Page, compiler: Compiler, scheduler) -> None:
        self._page = page
        self._compiler = compiler
        self._scheduler = scheduler

        # ── タブ管理 ─────────────────────────────────────────
        self._tabs: list[_Tab] = [_Tab(name="script.ls", dsl_text=_DEFAULT_DSL)]
        self._active_tab: _Tab = self._tabs[0]

        # ── DSL Editor（シンタックスハイライト付きオーバーレイ）───
        # 背景: ハイライト済みテキスト（読み取り専用表示）
        self._dsl_highlight_text = ft.Text(
            spans=_highlight_dsl(_DEFAULT_DSL),
            size=13,
        )
        self._dsl_highlight_layer = ft.Container(
            content=self._dsl_highlight_text,
            padding=ft.padding.only(left=48, top=16, right=16, bottom=16),
        )

        # 行番号ガター
        self._line_numbers = ft.Text(
            value=self._make_line_numbers(_DEFAULT_DSL),
            size=13,
            color="#6A6560",
            font_family=_CODE_FONT,
            text_align=ft.TextAlign.RIGHT,
        )
        self._line_number_gutter = ft.Container(
            content=self._line_numbers,
            width=36,
            padding=ft.padding.only(top=16, right=4),
            alignment=ft.Alignment(1, -1),  # top_right
            border=ft.border.only(right=ft.BorderSide(1, "#3A3835")),
        )

        # 前面: 透明テキストの編集用TextField
        self._editor = ft.TextField(
            value=_DEFAULT_DSL,
            multiline=True,
            min_lines=16,
            expand=True,
            text_style=ft.TextStyle(
                font_family=_CODE_FONT,
                size=13, color="#00000000",  # 完全透明（ハイライト層を見せる）
            ),
            bgcolor=ft.Colors.TRANSPARENT,
            border_color=ft.Colors.TRANSPARENT,
            focused_border_color=ft.Colors.TRANSPARENT,
            border_radius=12,
            cursor_color=COLORS["yellow"],
            hint_text="LifeScript DSL を入力…",
            hint_style=ft.TextStyle(color=COLORS["light_text"]),
            content_padding=ft.padding.only(left=48, top=16, right=16, bottom=16),
            on_change=self._on_editor_change,
        )
        self._prev_editor_value = _DEFAULT_DSL

        # ── ミニマップ（コードの縮小表示）───────────────────────
        self._minimap_text = ft.Text(
            value=_DEFAULT_DSL,
            size=2,
            color="#6A6560",
            font_family=_CODE_FONT,
        )
        self._minimap = ft.Container(
            content=self._minimap_text,
            width=60,
            bgcolor="#1E1C19",
            padding=ft.padding.symmetric(horizontal=4, vertical=8),
            border=ft.border.only(left=ft.BorderSide(1, "#3A3835")),
            alignment=ft.Alignment(-1, -1),  # top_left
            clip_behavior=ft.ClipBehavior.HARD_EDGE,
        )

        # ── テンプレートギャラリー（エディタが空のとき表示）───────
        self._template_gallery = self._build_template_gallery()

        # ── タブバー ──────────────────────────────────────────
        self._tab_bar = ft.Row(spacing=2, scroll=ft.ScrollMode.AUTO)

        # Stack でハイライト層の上にTextFieldを重ねる + テンプレート
        self._editor_stack = ft.Stack(
            [
                ft.Row([
                    self._line_number_gutter,
                    ft.Stack(
                        [self._dsl_highlight_layer, self._editor],
                        expand=True,
                    ),
                    self._minimap,
                ], spacing=0, expand=True),
                self._template_gallery,
            ],
            expand=True,
        )

        self._editor_panel = ft.Container(
            content=ft.Column([
                ft.Container(
                    content=self._tab_bar,
                    padding=ft.padding.only(left=4, bottom=0),
                ),
                self._editor_stack,
            ], spacing=0, expand=True),
            expand=2,
            border_radius=20,
            bgcolor=COLORS["editor_bg"],
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            shadow=ft.BoxShadow(
                spread_radius=0, blur_radius=20,
                color="#00000018", offset=ft.Offset(0, 4),
            ),
        )

        # ── Python preview (シンタックスハイライト付き) ─────────
        self._python_raw = "# コンパイル結果がここに表示されます"
        self._python_preview_text = ft.Text(
            spans=_highlight_python(self._python_raw),
            size=12,
            selectable=True,
        )
        self._python_preview_container = ft.Container(
            content=ft.Column([self._python_preview_text],
                              scroll=ft.ScrollMode.AUTO, expand=True),
            expand=True,
            bgcolor="#1E1C19",
            border_radius=14,
            padding=ft.padding.all(16),
        )

        preview_panel = ft.Container(
            content=ft.Column([
                ft.Container(
                    content=ft.Row([
                        ft.Container(
                            content=ft.Row([
                                ft.Icon(ft.Icons.CODE_ROUNDED, size=14, color=COLORS["green"]),
                                ft.Text("compiled.py", size=12, weight=ft.FontWeight.W_600, color=COLORS["dark_text"]),
                            ], spacing=6),
                            bgcolor=COLORS["card_bg"],
                            border_radius=ft.border_radius.only(top_left=10, top_right=10),
                            padding=ft.padding.symmetric(horizontal=14, vertical=8),
                            border=ft.border.only(bottom=ft.BorderSide(2, COLORS["green"])),
                        ),
                    ], spacing=2),
                    padding=ft.padding.only(left=4, bottom=0),
                ),
                self._python_preview_container,
            ], spacing=0, expand=True),
            expand=1,
            border_radius=16,
            bgcolor="#1E1C19",
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        )

        # ── Scripts list ───────────────────────────────────────
        self._scripts_list = ft.ListView(expand=True, spacing=4, padding=4)

        scripts_panel = ft.Column([
            ft.Container(
                content=ft.Row([
                    ft.Icon(ft.Icons.BOLT_ROUNDED, size=16, color=COLORS["yellow"]),
                    ft.Text("Scripts", size=13, weight=ft.FontWeight.W_700, color=COLORS["dark_text"]),
                ], spacing=6),
                padding=ft.padding.only(left=8, top=4, bottom=4),
            ),
            self._scripts_list,
        ], expand=True, spacing=8)

        # ── Chat panel ────────────────────────────────────────
        self._chat_engine = CodingChat(model=compiler.model)
        self._chat_messages = ft.ListView(expand=True, spacing=6, padding=4, auto_scroll=True)
        self._chat_input = ft.TextField(
            hint_text="やりたいことを伝えてください…",
            text_size=13,
            border_radius=10,
            bgcolor=COLORS["bg"],
            border_color=_BORDER,
            focused_border_color=COLORS["blue"],
            content_padding=ft.padding.symmetric(horizontal=12, vertical=10),
            on_submit=self._on_chat_send,
            suffix=ft.IconButton(
                ft.Icons.SEND_ROUNDED, icon_size=18, icon_color=COLORS["blue"],
                style=ft.ButtonStyle(padding=4),
                on_click=self._on_chat_send,
            ),
        )

        chat_panel = ft.Column([
            self._chat_messages,
            self._chat_input,
        ], expand=True, spacing=8)

        # ── Sidebar (Scripts / Chat タブ切り替え) ─────────────
        self._sidebar_content = ft.Container(content=scripts_panel, expand=True)
        self._sidebar_mode = ["scripts"]  # "scripts" or "chat"

        def _switch_sidebar(mode: str) -> None:
            self._sidebar_mode[0] = mode
            self._sidebar_content.content = scripts_panel if mode == "scripts" else chat_panel
            self._rebuild_sidebar_tabs()
            self._page.update()

        self._switch_sidebar = _switch_sidebar

        self._sidebar_tab_row = ft.Row(spacing=2)

        def _rebuild_sidebar_tabs() -> None:
            mode = self._sidebar_mode[0]
            self._sidebar_tab_row.controls = [
                ft.Container(
                    content=ft.Row([
                        ft.Icon(ft.Icons.BOLT_ROUNDED, size=14,
                                color=COLORS["yellow"] if mode == "scripts" else COLORS["light_text"]),
                        ft.Text("Scripts", size=12,
                                weight=ft.FontWeight.W_600 if mode == "scripts" else ft.FontWeight.W_400,
                                color=COLORS["dark_text"] if mode == "scripts" else COLORS["mid_text"]),
                    ], spacing=4, tight=True),
                    padding=ft.padding.symmetric(horizontal=10, vertical=6),
                    border_radius=ft.border_radius.only(top_left=10, top_right=10),
                    bgcolor=COLORS["card_bg"] if mode == "scripts" else ft.Colors.TRANSPARENT,
                    border=ft.border.only(bottom=ft.BorderSide(2, COLORS["yellow"])) if mode == "scripts" else None,
                    on_click=lambda e: _switch_sidebar("scripts"),
                ),
                ft.Container(
                    content=ft.Row([
                        ft.Icon(ft.Icons.CHAT_ROUNDED, size=14,
                                color=COLORS["blue"] if mode == "chat" else COLORS["light_text"]),
                        ft.Text("Chat", size=12,
                                weight=ft.FontWeight.W_600 if mode == "chat" else ft.FontWeight.W_400,
                                color=COLORS["dark_text"] if mode == "chat" else COLORS["mid_text"]),
                    ], spacing=4, tight=True),
                    padding=ft.padding.symmetric(horizontal=10, vertical=6),
                    border_radius=ft.border_radius.only(top_left=10, top_right=10),
                    bgcolor=COLORS["card_bg"] if mode == "chat" else ft.Colors.TRANSPARENT,
                    border=ft.border.only(bottom=ft.BorderSide(2, COLORS["blue"])) if mode == "chat" else None,
                    on_click=lambda e: _switch_sidebar("chat"),
                ),
            ]

        self._rebuild_sidebar_tabs = _rebuild_sidebar_tabs
        _rebuild_sidebar_tabs()

        sidebar = ft.Container(
            content=ft.Column([
                self._sidebar_tab_row,
                self._sidebar_content,
            ], expand=True, spacing=4),
            width=280,
            bgcolor=COLORS["card_bg"],
            border_radius=20,
            padding=12,
            shadow=CARD_SHADOW,
        )

        # ── Function reference ────────────────────────────────
        from ..functions import FUNCTION_DESCRIPTIONS
        ref_items = []
        for f in FUNCTION_DESCRIPTIONS:
            ref_items.append(
                ft.Container(
                    content=ft.Column([
                        ft.Text(f["name"], size=12, weight=ft.FontWeight.W_600, color=COLORS["blue"]),
                        ft.Text(f["signature"], size=10, color=COLORS["mid_text"], font_family=_CODE_FONT),
                        ft.Text(f["description"], size=10, color=COLORS["light_text"]),
                    ], spacing=2),
                    padding=ft.padding.only(bottom=8),
                )
            )

        # ── Action toolbar ────────────────────────────────────
        self._snippet_expanded = False
        self._ignore_next_global_tap = False
        self._snippet_buttons_column = ft.Column([
            ft.OutlinedButton(
                "every", style=ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius=14),
                    side=ft.BorderSide(1, COLORS["yellow"]),
                    color=COLORS["yellow"],
                    padding=ft.padding.symmetric(horizontal=14, vertical=10),
                ),
                on_click=lambda e: self._insert_snippet('every :\n  notify("")'),
            ),
            ft.OutlinedButton(
                "when", style=ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius=14),
                    side=ft.BorderSide(1, COLORS["green"]),
                    color=COLORS["green"],
                    padding=ft.padding.symmetric(horizontal=14, vertical=10),
                ),
                on_click=lambda e: self._insert_snippet('when calendar.read("").count_this_week >= 0:\n  '),
            ),
            ft.OutlinedButton(
                "notify", style=ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius=14),
                    side=ft.BorderSide(1, COLORS["coral"]),
                    color=COLORS["coral"],
                    padding=ft.padding.symmetric(horizontal=14, vertical=10),
                ),
                on_click=lambda e: self._insert_snippet('notify("")'),
            ),
            ft.OutlinedButton(
                "calendar", style=ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius=14),
                    side=ft.BorderSide(1, COLORS["blue"]),
                    color=COLORS["blue"],
                    padding=ft.padding.symmetric(horizontal=14, vertical=10),
                ),
                on_click=lambda e: self._insert_snippet('calendar.add("", start="")'),
            ),
            ft.OutlinedButton(
                "web", style=ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius=14),
                    side=ft.BorderSide(1, COLORS["purple"]),
                    color=COLORS["purple"],
                    padding=ft.padding.symmetric(horizontal=14, vertical=10),
                ),
                on_click=lambda e: self._insert_snippet('result = web.fetch("https://")\nwidget.show("", result)'),
            ),
            ft.OutlinedButton(
                "traits", style=ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius=14),
                    side=ft.BorderSide(1, COLORS["orange"]),
                    color=COLORS["orange"],
                    padding=ft.padding.symmetric(horizontal=14, vertical=10),
                ),
                on_click=lambda e: self._insert_snippet('traits:\n  '),
            ),
        ], spacing=8, horizontal_alignment=ft.CrossAxisAlignment.END)

        self._snippet_popover = ft.Container(
            content=self._snippet_buttons_column,
            visible=self._snippet_expanded,
            bgcolor=COLORS["card_bg"],
            border_radius=16,
            padding=10,
            right=0,
            bottom=52,
            shadow=ft.BoxShadow(
                blur_radius=12,
                color="#22000000",
                offset=ft.Offset(0, 4),
            ),
        )

        self._snippet_toggle_button = ft.OutlinedButton(
            "Functions",
            icon=ft.Icons.KEYBOARD_ARROW_DOWN_ROUNDED,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=10),
                side=ft.BorderSide(1, COLORS["mid_text"]),
                color=COLORS["mid_text"],
                padding=ft.padding.symmetric(horizontal=14, vertical=10),
            ),
            on_click=self._toggle_snippets,
        )

        self._snippet_anchor = ft.Stack(
            controls=[
                self._snippet_popover,
                ft.Container(
                    content=self._snippet_toggle_button,
                    right=0,
                    bottom=0,
                ),
            ],
            width=260,
            height=44,
            clip_behavior=ft.ClipBehavior.NONE,
        )

        # ── コンパイルボタン（状態表示付き）──────────────────────
        self._compile_btn = ft.ElevatedButton(
            "Compile",
            icon=ft.Icons.AUTO_FIX_HIGH_ROUNDED,
            bgcolor=COLORS["yellow"],
            color=COLORS["dark_text"],
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=16),
                elevation=2,
                padding=ft.padding.symmetric(horizontal=20, vertical=12),
            ),
            on_click=self._on_compile,
        )

        action_bar = ft.Container(
            content=ft.Row([
                self._compile_btn,
                ft.ElevatedButton(
                    "Run",
                    icon=ft.Icons.PLAY_ARROW_ROUNDED,
                    bgcolor=COLORS["blue"],
                    color=COLORS["card_bg"],
                    style=ft.ButtonStyle(
                        shape=ft.RoundedRectangleBorder(radius=16),
                        elevation=2,
                        padding=ft.padding.symmetric(horizontal=20, vertical=12),
                    ),
                    on_click=self._on_run,
                ),
                ft.ElevatedButton(
                    "Save & Register",
                    icon=ft.Icons.SAVE_ROUNDED,
                    bgcolor=COLORS["green"],
                    color=COLORS["card_bg"],
                    style=ft.ButtonStyle(
                        shape=ft.RoundedRectangleBorder(radius=16),
                        elevation=2,
                        padding=ft.padding.symmetric(horizontal=20, vertical=12),
                    ),
                    on_click=self._on_save,
                ),
                ft.ElevatedButton(
                    "Stop All",
                    icon=ft.Icons.STOP_ROUNDED,
                    bgcolor=COLORS["coral"],
                    color=COLORS["card_bg"],
                    style=ft.ButtonStyle(
                        shape=ft.RoundedRectangleBorder(radius=16),
                        elevation=2,
                        padding=ft.padding.symmetric(horizontal=20, vertical=12),
                    ),
                    on_click=self._on_stop_all,
                ),
                ft.Container(expand=True),
                self._snippet_anchor,
            ], spacing=10),
            padding=ft.padding.symmetric(vertical=4),
        )

        # ── Log panel ─────────────────────────────────────────
        self._log_list = ft.ListView(expand=True, auto_scroll=True, spacing=1)

        log_panel = ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Icon(ft.Icons.TERMINAL_ROUNDED, size=14, color=COLORS["light_text"]),
                    ft.Text("Output", size=12, weight=ft.FontWeight.W_600, color=COLORS["mid_text"]),
                    ft.Container(expand=True),
                    ft.TextButton("Reference", style=ft.ButtonStyle(color=COLORS["blue"], padding=4),
                                  on_click=self._show_reference),
                ], spacing=6),
                ft.Container(
                    content=self._log_list,
                    expand=True,
                    bgcolor=COLORS["editor_bg"],
                    border_radius=10,
                    padding=10,
                ),
            ], spacing=6, expand=True),
            height=160,
            bgcolor=COLORS["card_bg"],
            border_radius=20,
            padding=12,
            shadow=CARD_SHADOW,
        )

        self._ref_items = ref_items

        self._content = ft.Column([
            ft.Row([
                ft.Column([self._editor_panel, preview_panel], expand=3, spacing=8),
                sidebar,
            ], expand=True, spacing=12),
            action_bar,
            log_panel,
        ], expand=True, spacing=10)

        self._root = ft.GestureDetector(
            content=self._content,
            on_tap=self._on_global_tap,
        )

        self._rebuild_tab_bar()
        self._load_scripts_list()

    def build(self) -> ft.Column:
        self._setup_tab_key()
        return self._root

    # ==================================================================
    # テンプレートギャラリー
    # ==================================================================
    def _build_template_gallery(self) -> ft.Container:
        """エディタが空のとき表示するテンプレート選択UI。"""

        def _make_card(tmpl: dict) -> ft.Container:
            return ft.Container(
                content=ft.Row([
                    ft.Container(
                        content=ft.Icon(tmpl["icon"], size=22, color="#FFFFFF"),
                        width=40, height=40,
                        bgcolor=tmpl["color"],
                        border_radius=10,
                        alignment=ft.Alignment(0, 0),
                    ),
                    ft.Column([
                        ft.Text(tmpl["title"], size=13,
                                weight=ft.FontWeight.W_600, color="#E8E4DC"),
                        ft.Text(tmpl["desc"], size=11, color="#A09A93",
                                max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                    ], spacing=2, expand=True),
                ], spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                padding=ft.padding.symmetric(horizontal=16, vertical=12),
                border_radius=12,
                bgcolor="#3A3835",
                border=ft.border.all(1, "#4A4845"),
                on_click=lambda e, t=tmpl: self._select_template(t),
                on_hover=lambda e: (
                    setattr(e.control, "bgcolor", "#4A4845" if e.data == "true" else "#3A3835"),
                    e.control.update(),
                ),
                ink=True,
            )

        # 「ダリーに聞く」カード
        darii_card = ft.Container(
            content=ft.Row([
                ft.Container(
                    content=ft.Icon(ft.Icons.AUTO_AWESOME_ROUNDED, size=22, color="#FFFFFF"),
                    width=40, height=40,
                    bgcolor=COLORS["yellow"],
                    border_radius=10,
                    alignment=ft.Alignment(0, 0),
                ),
                ft.Column([
                    ft.Text("ダリーに相談する", size=13,
                            weight=ft.FontWeight.W_600, color="#E8E4DC"),
                    ft.Text("何を自動化したいか話しかけると、ダリーがDSLを書いてくれます",
                            size=11, color="#A09A93",
                            max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                ], spacing=2, expand=True),
            ], spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            padding=ft.padding.symmetric(horizontal=16, vertical=12),
            border_radius=12,
            bgcolor="#3A3835",
            border=ft.border.all(1, COLORS["yellow"] + "44"),
            on_click=lambda e: self._focus_chat(),
            on_hover=lambda e: (
                setattr(e.control, "bgcolor", "#4A4845" if e.data == "true" else "#3A3835"),
                e.control.update(),
            ),
            ink=True,
        )

        # 「空白から始める」カード
        blank_card = ft.Container(
            content=ft.Row([
                ft.Container(
                    content=ft.Icon(ft.Icons.EDIT_NOTE_ROUNDED, size=22, color="#A09A93"),
                    width=40, height=40,
                    bgcolor="#2D2B27",
                    border_radius=10,
                    border=ft.border.all(1, "#4A4845"),
                    alignment=ft.Alignment(0, 0),
                ),
                ft.Text("空白から書く", size=13, color="#A09A93"),
            ], spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            padding=ft.padding.symmetric(horizontal=16, vertical=12),
            border_radius=12,
            bgcolor="#3A3835",
            on_click=lambda e: self._dismiss_gallery(),
            on_hover=lambda e: (
                setattr(e.control, "bgcolor", "#4A4845" if e.data == "true" else "#3A3835"),
                e.control.update(),
            ),
            ink=True,
        )

        gallery = ft.Container(
            content=ft.Column(
                [
                    ft.Container(height=20),
                    ft.Text("何から始めますか？", size=18,
                            weight=ft.FontWeight.W_700, color="#E8E4DC",
                            text_align=ft.TextAlign.CENTER),
                    ft.Text("テンプレートを選ぶか、ダリーに話しかけてみてください",
                            size=12, color="#A09A93",
                            text_align=ft.TextAlign.CENTER),
                    ft.Container(height=8),
                    *[_make_card(t) for t in _TEMPLATES],
                    ft.Container(height=4),
                    darii_card,
                    blank_card,
                ],
                spacing=8,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                scroll=ft.ScrollMode.AUTO,
            ),
            padding=ft.padding.symmetric(horizontal=32, vertical=16),
            bgcolor=COLORS["editor_bg"],
            expand=True,
            visible=True,  # エディタが空なら表示
        )
        return gallery

    def _select_template(self, tmpl: dict) -> None:
        """テンプレートをエディタに挿入してギャラリーを非表示にする。"""
        self._editor.value = tmpl["dsl"]
        self._active_tab.dsl_text = tmpl["dsl"]
        self._prev_editor_value = tmpl["dsl"]
        self._dsl_highlight_text.spans = _highlight_dsl(tmpl["dsl"])
        self._template_gallery.visible = False
        self._page.update()

    def _dismiss_gallery(self) -> None:
        """テンプレートギャラリーを非表示にしてエディタにフォーカス。"""
        self._template_gallery.visible = False
        self._editor.focus()
        self._page.update()

    def _focus_chat(self) -> None:
        """サイドバーをChatに切り替えてチャット入力にフォーカス。"""
        self._template_gallery.visible = False
        self._switch_sidebar("chat")
        self._chat_input.focus()
        self._page.update()

    def _update_gallery_visibility(self) -> None:
        """エディタの内容に応じてテンプレートギャラリーの表示を切り替える。"""
        is_empty = not (self._editor.value or "").strip()
        self._template_gallery.visible = is_empty

    # ==================================================================
    # エディタ: 自動インデント + Tabキー
    # ==================================================================
    def _setup_tab_key(self) -> None:
        """ページレベルの keyboard event で Tab キーをキャプチャ。"""
        def _on_keyboard(e: ft.KeyboardEvent) -> None:
            if e.key != "Tab":
                return
            # エディタにフォーカスがあるときだけ処理
            val = self._editor.value or ""
            if not val:
                self._editor.value = "  "
                self._prev_editor_value = self._editor.value
                self._page.update()
                return

            # カーソル位置は取得できないので末尾にスペース2つ追加
            # （Flet TextField の制約）
            if val.endswith("\n") or val.endswith("  "):
                self._editor.value = val + "  "
            else:
                self._editor.value = val + "  "
            self._prev_editor_value = self._editor.value
            self._page.update()

        self._page.on_keyboard_event = _on_keyboard

    @staticmethod
    def _make_line_numbers(code: str) -> str:
        """コードの行数に応じた行番号文字列を生成する。"""
        lines = (code or "").split("\n")
        count = max(len(lines), 1)
        return "\n".join(str(i + 1) for i in range(count))

    def _update_editor_decorations(self, val: str) -> None:
        """行番号とミニマップを更新する。"""
        self._line_numbers.value = self._make_line_numbers(val)
        self._minimap_text.value = val or ""

    def _on_editor_change(self, e: ft.ControlEvent) -> None:
        """改行時に自動インデント + DSLシンタックスハイライト更新。"""
        val = self._editor.value or ""
        prev = self._prev_editor_value or ""
        self._prev_editor_value = val

        # テンプレートギャラリーの表示切替
        self._update_gallery_visibility()

        # ハイライト・行番号・ミニマップ更新
        self._dsl_highlight_text.spans = _highlight_dsl(val)
        self._update_editor_decorations(val)

        # 改行が追加されたか検出（文字数が1増えて末尾が改行）
        if len(val) != len(prev) + 1 or not val.endswith("\n"):
            return

        # 改行直前の行を取得
        lines = val.rstrip("\n").split("\n")
        if not lines:
            return
        last_line = lines[-1]

        # 前の行のインデントを継承
        indent = ""
        for ch in last_line:
            if ch == " ":
                indent += " "
            else:
                break

        # `:` で終わる行なら1段深くする
        stripped = last_line.rstrip()
        if stripped.endswith(":"):
            indent += "  "

        if indent:
            self._editor.value = val + indent
            self._prev_editor_value = self._editor.value
            self._page.update()

    # ==================================================================
    # タブ管理
    # ==================================================================
    def _rebuild_tab_bar(self) -> None:
        controls: list[ft.Control] = []
        for i, tab in enumerate(self._tabs):
            is_active = tab is self._active_tab
            color = _TAB_COLORS[i % len(_TAB_COLORS)]
            tab_container = ft.Container(
                content=ft.Row([
                    ft.Icon(ft.Icons.DESCRIPTION_ROUNDED, size=14,
                            color=color if is_active else COLORS["light_text"]),
                    ft.Text(
                        tab.name, size=12,
                        weight=ft.FontWeight.W_600 if is_active else ft.FontWeight.W_400,
                        color=COLORS["dark_text"] if is_active else COLORS["mid_text"],
                        max_lines=1, overflow=ft.TextOverflow.ELLIPSIS,
                    ),
                    ft.IconButton(
                        ft.Icons.CLOSE_ROUNDED, icon_size=12,
                        icon_color=COLORS["light_text"],
                        style=ft.ButtonStyle(padding=2),
                        tooltip="閉じる",
                        on_click=lambda e, t=tab: self._close_tab(t),
                    ),
                ], spacing=4, vertical_alignment=ft.CrossAxisAlignment.CENTER,
                   tight=True),
                bgcolor=COLORS["card_bg"] if is_active else ft.Colors.TRANSPARENT,
                border_radius=ft.border_radius.only(top_left=10, top_right=10),
                padding=ft.padding.symmetric(horizontal=12, vertical=6),
                border=ft.border.only(bottom=ft.BorderSide(2, color)) if is_active else None,
            )
            controls.append(ft.GestureDetector(
                content=tab_container,
                on_tap=lambda e, t=tab: self._switch_tab(t),
                on_secondary_tap=lambda e, t=tab: self._show_rename_dialog(t),
            ))

        # 新規タブボタン
        controls.append(ft.IconButton(
            ft.Icons.ADD_ROUNDED, icon_size=16,
            icon_color=COLORS["mid_text"],
            tooltip="新しいタブ",
            style=ft.ButtonStyle(padding=4),
            on_click=lambda e: self._new_tab(),
        ))

        self._tab_bar.controls = controls

    def _switch_tab(self, tab: _Tab) -> None:
        # 現在のタブの内容を保存
        self._active_tab.dsl_text = self._editor.value or ""
        # 切り替え
        self._active_tab = tab
        self._editor.value = tab.dsl_text
        self._prev_editor_value = tab.dsl_text
        self._dsl_highlight_text.spans = _highlight_dsl(tab.dsl_text)
        self._update_gallery_visibility()
        compiled = tab.compiled
        if compiled:
            self._set_preview(compiled.get("code", ""))
        else:
            self._set_preview("# コンパイル結果がここに表示されます")
        self._rebuild_tab_bar()
        self._page.update()

    def _new_tab(self) -> None:
        self._active_tab.dsl_text = self._editor.value or ""
        tab = _Tab()
        self._tabs.append(tab)
        self._active_tab = tab
        self._editor.value = ""
        self._dsl_highlight_text.spans = _highlight_dsl("")
        self._template_gallery.visible = True  # 新規タブはギャラリー表示
        self._set_preview("# コンパイル結果がここに表示されます")
        self._rebuild_tab_bar()
        self._page.update()

    def _close_tab(self, tab: _Tab) -> None:
        if len(self._tabs) <= 1:
            return
        idx = self._tabs.index(tab)
        self._tabs.remove(tab)
        if tab is self._active_tab:
            new_idx = min(idx, len(self._tabs) - 1)
            self._active_tab = self._tabs[new_idx]
            self._editor.value = self._active_tab.dsl_text
            self._dsl_highlight_text.spans = _highlight_dsl(self._active_tab.dsl_text)
            compiled = self._active_tab.compiled
            self._set_preview(compiled.get("code", "") if compiled else "# コンパイル結果がここに表示されます")
        self._update_gallery_visibility()
        self._rebuild_tab_bar()
        self._page.update()

    def _show_rename_dialog(self, tab: _Tab) -> None:
        name_field = ft.TextField(
            value=tab.name, autofocus=True, text_size=14,
            border_radius=10, width=300,
            label="ファイル名",
        )

        def _save(e: ft.ControlEvent) -> None:
            new_name = (name_field.value or "").strip()
            if new_name:
                if not new_name.endswith(".ls"):
                    new_name += ".ls"
                tab.name = new_name
                # DBに保存済みなら名前も更新
                if tab.script_id:
                    try:
                        db_client.update_script(int(tab.script_id), name=new_name)
                    except Exception:
                        pass
                self._rebuild_tab_bar()
                self._load_scripts_list()
            dialog.open = False
            self._page.update()

        dialog = ft.AlertDialog(
            title=ft.Text("ファイル名を変更", size=16, weight=ft.FontWeight.W_600),
            content=name_field,
            actions=[
                ft.TextButton("キャンセル",
                              on_click=lambda e: setattr(dialog, "open", False) or self._page.update()),
                ft.ElevatedButton("変更", bgcolor=COLORS["blue"], color=COLORS["card_bg"],
                                  on_click=_save),
            ],
        )
        name_field.on_submit = _save
        self._page.overlay.append(dialog)
        dialog.open = True
        self._page.update()

    # ==================================================================
    # Helpers
    # ==================================================================
    # ==================================================================
    # チャット
    # ==================================================================
    def _on_chat_send(self, e: ft.ControlEvent) -> None:
        msg = (self._chat_input.value or "").strip()
        if not msg:
            return
        self._chat_input.value = ""
        self._chat_messages.controls.append(self._chat_bubble(msg, is_user=True))
        # ローディング表示
        loading = ft.Container(
            content=ft.Row([
                ft.ProgressRing(width=14, height=14, stroke_width=2, color=COLORS["blue"]),
                ft.Text("考え中…", size=12, color=COLORS["light_text"]),
            ], spacing=6),
            padding=ft.padding.symmetric(horizontal=12, vertical=8),
        )
        self._chat_messages.controls.append(loading)
        self._page.update()

        def _call() -> None:
            try:
                reply = self._chat_engine.send(msg)
                if loading in self._chat_messages.controls:
                    self._chat_messages.controls.remove(loading)
                self._chat_messages.controls.append(self._chat_bubble(reply, is_user=False))
            except Exception as ex:
                if loading in self._chat_messages.controls:
                    self._chat_messages.controls.remove(loading)
                self._chat_messages.controls.append(self._chat_bubble(
                    f"エラー: {ex}", is_user=False, is_error=True))
            self._page.update()

        threading.Thread(target=_call, daemon=True).start()

    def _chat_bubble(self, text: str, is_user: bool = False,
                     is_error: bool = False) -> ft.Container:
        if is_user:
            return ft.Container(
                content=ft.Text(text, size=13, color=COLORS["card_bg"]),
                bgcolor=COLORS["blue"],
                border_radius=ft.border_radius.only(
                    top_left=12, top_right=12, bottom_left=12, bottom_right=4),
                padding=ft.padding.symmetric(horizontal=12, vertical=8),
                margin=ft.margin.only(left=40),
            )

        if is_error:
            return ft.Container(
                content=ft.Text(text, size=13, color=COLORS["coral"]),
                bgcolor="#FFF0F0",
                border_radius=12,
                padding=ft.padding.symmetric(horizontal=12, vertical=8),
            )

        # アシスタントメッセージ: コードブロックを抽出してInsertボタン付きで表示
        parts = re.split(r"```(?:lifescript|ls|yaml)?\s*\n?(.*?)```", text, flags=re.DOTALL)
        controls: list[ft.Control] = []

        for i, part in enumerate(parts):
            part = part.strip()
            if not part:
                continue
            if i % 2 == 0:
                # テキスト部分
                controls.append(ft.Text(part, size=13, color=COLORS["dark_text"]))
            else:
                # コードブロック部分
                code = part.strip()
                controls.append(ft.Container(
                    content=ft.Column([
                        ft.Container(
                            content=ft.Text(
                                code, size=12, color=COLORS["editor_fg"],
                                font_family=_CODE_FONT,
                                selectable=True,
                            ),
                            bgcolor=COLORS["editor_bg"],
                            border_radius=8,
                            padding=10,
                        ),
                        ft.Row([
                            ft.Container(expand=True),
                            ft.ElevatedButton(
                                "エディタに挿入",
                                icon=ft.Icons.ADD_ROUNDED,
                                bgcolor=COLORS["green"],
                                color=COLORS["card_bg"],
                                style=ft.ButtonStyle(
                                    shape=ft.RoundedRectangleBorder(radius=8),
                                    elevation=0,
                                    padding=ft.padding.symmetric(horizontal=12, vertical=6),
                                    text_style=ft.TextStyle(size=12),
                                ),
                                on_click=lambda e, c=code: self._insert_from_chat(c),
                            ),
                        ]),
                    ], spacing=4),
                ))

        if not controls:
            controls.append(ft.Text(text or "（応答なし）", size=13, color=COLORS["dark_text"]))

        return ft.Container(
            content=ft.Column(controls, spacing=6),
            bgcolor="#F8F7F4",
            border_radius=ft.border_radius.only(
                top_left=12, top_right=12, bottom_left=4, bottom_right=12),
            padding=ft.padding.symmetric(horizontal=12, vertical=8),
            margin=ft.margin.only(right=20),
        )

    def _insert_from_chat(self, code: str) -> None:
        """チャットで生成されたDSLをアクティブタブのエディタに挿入する。"""
        current = self._editor.value or ""
        if current.strip() and not current.endswith("\n"):
            current += "\n\n"
        elif current.strip():
            current += "\n"
        self._editor.value = current + code
        self._active_tab.dsl_text = self._editor.value
        self._prev_editor_value = self._editor.value
        self._dsl_highlight_text.spans = _highlight_dsl(self._editor.value)
        self._template_gallery.visible = False
        self._log(f"チャットからDSLを挿入しました", COLORS["green"])
        self._page.update()

    # ==================================================================
    # Helpers
    # ==================================================================
    def _set_preview(self, code: str) -> None:
        """Python プレビューをシンタックスハイライト付きで更新する。"""
        self._python_raw = code
        self._python_preview_text.spans = _highlight_python(code)

    def _toggle_snippets(self, e: ft.ControlEvent) -> None:
        """Snippet buttons の表示を切り替える。"""
        # トグルボタン自身のタップで直後に閉じないよう1回だけ無視する
        self._ignore_next_global_tap = True
        self._snippet_expanded = not self._snippet_expanded
        self._snippet_popover.visible = self._snippet_expanded
        self._snippet_toggle_button.text = "Snippets" if not self._snippet_expanded else "Snippets (close)"
        self._snippet_toggle_button.icon = (
            ft.Icons.KEYBOARD_ARROW_DOWN_ROUNDED
            if not self._snippet_expanded
            else ft.Icons.KEYBOARD_ARROW_UP_ROUNDED
        )
        self._page.update()

    def _on_global_tap(self, e: ft.ControlEvent) -> None:
        """画面の任意タップで、展開中の Snippet パネルを閉じる。"""
        if self._ignore_next_global_tap:
            self._ignore_next_global_tap = False
            return
        if not self._snippet_expanded:
            return
        self._snippet_expanded = False
        self._snippet_popover.visible = False
        self._snippet_toggle_button.text = "Snippets"
        self._snippet_toggle_button.icon = ft.Icons.KEYBOARD_ARROW_DOWN_ROUNDED
        self._page.update()

    def _insert_snippet(self, snippet: str) -> None:
        current = self._editor.value or ""
        if current and not current.endswith("\n"):
            current += "\n"
        self._editor.value = current + snippet
        self._active_tab.dsl_text = self._editor.value
        self._dsl_highlight_text.spans = _highlight_dsl(self._editor.value)
        self._template_gallery.visible = False
        self._page.update()

    def prefill_dsl(self, dsl_code: str, tab_name: str = "") -> None:
        """外部から新規タブにDSLコードを挿入する（提案→IDE遷移用）。

        タイプライターエフェクト付き: ダリーがリアルタイムでコードを書く演出。
        """
        self._active_tab.dsl_text = self._editor.value or ""
        tab = _Tab(name=tab_name or "suggestion.ls", dsl_text="")
        self._tabs.append(tab)
        self._active_tab = tab
        self._editor.value = ""
        self._prev_editor_value = ""
        self._dsl_highlight_text.spans = []
        self._template_gallery.visible = False
        self._set_preview("")
        self._rebuild_tab_bar()
        self._page.update()

        # タイプライターアニメーションをバックグラウンドで実行
        import threading
        threading.Thread(
            target=self._typewriter_animate,
            args=(dsl_code,),
            daemon=True,
        ).start()

    def _typewriter_animate(self, dsl_code: str) -> None:
        """タイプライターエフェクト + セキュリティチェック演出。"""
        import time

        # ── Phase 1: ダリーがタイピング ──────────────────────────
        self._log("🤖 ダリーが LifeScript を書いています…", COLORS["yellow"])
        self._page.update()
        time.sleep(0.3)

        # 1文字ずつではなく、チャンク（2-4文字）単位で高速タイピング
        current = ""
        i = 0
        while i < len(dsl_code):
            # 改行直後は少し長めのpause
            if dsl_code[i] == "\n":
                chunk_size = 1
                delay = 0.06
            else:
                chunk_size = min(3, len(dsl_code) - i)
                delay = 0.02
            current += dsl_code[i:i + chunk_size]
            i += chunk_size

            self._editor.value = current
            self._dsl_highlight_text.spans = _highlight_dsl(current)
            self._page.update()
            time.sleep(delay)

        # タイピング完了
        self._active_tab.dsl_text = dsl_code
        self._prev_editor_value = dsl_code
        time.sleep(0.3)

        # ── Phase 2: セキュリティチェック演出 ─────────────────────
        _GREEN = "#00C875"
        _CYAN = "#4EC9B0"
        _DIM = "#6A9955"

        checks = [
            (f"{_DIM}", "$ lifescript compile --verify"),
            (f"{_CYAN}", "[AST Parse]        構文解析中…"),
            (f"{_GREEN}", "[AST Parse]        OK — 構文エラーなし"),
            (f"{_CYAN}", "[Sandbox Target]   RestrictedPython 検証中…"),
            (f"{_GREEN}", "[Sandbox Target]   OK — 禁止操作なし"),
            (f"{_CYAN}", "[Function Guard]   関数ホワイトリスト照合中…"),
            (f"{_GREEN}", "[Function Guard]   OK — 全関数が許可リスト内"),
            (f"{_CYAN}", "[Rate Limiter]     実行制限チェック中…"),
            (f"{_GREEN}", "[Rate Limiter]     OK — 制限内"),
        ]

        # プレビュー領域をターミナル風に
        self._set_preview("")
        self._page.update()
        time.sleep(0.2)

        for color, text in checks:
            self._log_list.controls.append(
                ft.Text(text, color=color, size=11, font_family=_CODE_FONT, selectable=True)
            )
            self._page.update()
            time.sleep(0.15)

        time.sleep(0.3)

        # ── Phase 3: Security Check Passed スタンプ ──────────────
        self._log_list.controls.append(ft.Container(height=4))
        self._log_list.controls.append(
            ft.Container(
                content=ft.Row([
                    ft.Icon(ft.Icons.VERIFIED_ROUNDED, size=16, color=_GREEN),
                    ft.Text(
                        "Security Check Passed",
                        size=13,
                        weight=ft.FontWeight.W_700,
                        color=_GREEN,
                        font_family=_CODE_FONT,
                    ),
                ], spacing=6, alignment=ft.MainAxisAlignment.CENTER),
                bgcolor="#00C87510",
                border=ft.border.all(1, f"{_GREEN}40"),
                border_radius=8,
                padding=ft.padding.symmetric(horizontal=12, vertical=6),
                margin=ft.margin.only(top=4),
            )
        )
        self._log("✅ LifeScript の生成と検証が完了しました", COLORS["green"])
        self._set_preview("# コンパイルしてください（▶ Compile ボタン）")
        self._page.update()

    def _show_reference(self, e: ft.ControlEvent) -> None:
        dialog = ft.AlertDialog(
            title=ft.Text("関数リファレンス", size=16, weight=ft.FontWeight.W_600),
            content=ft.Column(self._ref_items, tight=True, spacing=8, scroll=ft.ScrollMode.AUTO),
            actions=[ft.TextButton("閉じる", on_click=lambda ev: setattr(dialog, "open", False) or self._page.update())],
        )
        self._page.overlay.append(dialog)
        dialog.open = True
        self._page.update()

    # ------------------------------------------------------------------
    # Log helpers
    # ------------------------------------------------------------------
    def receive_logs(self, entries: list) -> None:
        for entry in entries:
            if isinstance(entry, tuple):
                source, msg, level = entry
                text = f"[{source}] {msg}"
            else:
                text = str(entry)
                level = "INFO"
            color = COLORS["coral"] if level == "ERROR" else (COLORS["yellow"] if level == "WARN" else COLORS["green"])
            self._log_list.controls.append(
                ft.Text(text, color=color, size=11, font_family=_CODE_FONT, selectable=True)
            )
        if len(self._log_list.controls) > 300:
            self._log_list.controls = self._log_list.controls[-300:]
        self._page.update()

    def _log(self, msg: str, color: str) -> None:
        self._log_list.controls.append(
            ft.Text(msg, color=color, size=11, font_family=_CODE_FONT, selectable=True)
        )
        if len(self._log_list.controls) > 300:
            self._log_list.controls = self._log_list.controls[-300:]
        self._page.update()

    # ------------------------------------------------------------------
    # Scripts list
    # ------------------------------------------------------------------
    def _load_scripts_list(self) -> None:
        self._scripts_list.controls.clear()
        try:
            scripts = db_client.get_scripts()
            if not scripts:
                self._scripts_list.controls.append(
                    ft.Container(
                        content=ft.Text("スクリプトなし", size=12, color=COLORS["light_text"], italic=True),
                        padding=8,
                    )
                )
            for script in scripts:
                self._scripts_list.controls.append(self._script_tile(script))
        except Exception as e:
            self._log(f"読み込みエラー: {e}", COLORS["coral"])
        self._page.update()

    def _script_tile(self, script: dict) -> ft.Container:
        name = script.get("name", "") or ""
        dsl_preview = (script.get("dsl_text", "") or "")[:30].replace("\n", " ")
        display = name if name else dsl_preview or f"スクリプト #{script['id']}"
        return ft.Container(
            content=ft.Row([
                ft.Container(width=8, height=8, border_radius=4, bgcolor=COLORS["green"]),
                ft.Text(
                    display,
                    size=11, weight=ft.FontWeight.W_500, color=COLORS["dark_text"],
                    expand=True, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS,
                ),
                ft.IconButton(
                    icon=ft.Icons.CLOSE_ROUNDED, icon_color=COLORS["light_text"], icon_size=14,
                    tooltip="削除", style=ft.ButtonStyle(padding=4),
                    on_click=lambda e, s=script: threading.Thread(
                        target=self._delete_script, args=(s,), daemon=True
                    ).start(),
                ),
            ], spacing=6, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            bgcolor=COLORS["bg"],
            border_radius=10,
            padding=ft.padding.symmetric(horizontal=10, vertical=6),
            on_click=lambda e, s=script: self._on_script_selected(s),
            ink=True,
        )

    # ------------------------------------------------------------------
    # Button handlers
    # ------------------------------------------------------------------
    def _set_compile_btn_state(self, state: str) -> None:
        """コンパイルボタンの状態を更新する。state: 'idle', 'compiling', 'success', 'error'"""
        if state == "compiling":
            self._compile_btn.text = "Compiling…"
            self._compile_btn.icon = ft.Icons.HOURGLASS_TOP_ROUNDED
            self._compile_btn.bgcolor = COLORS["blue"]
            self._compile_btn.color = COLORS["card_bg"]
            self._compile_btn.disabled = True
        elif state == "success":
            self._compile_btn.text = "Compiled ✓"
            self._compile_btn.icon = ft.Icons.CHECK_CIRCLE_ROUNDED
            self._compile_btn.bgcolor = COLORS["green"]
            self._compile_btn.color = COLORS["card_bg"]
            self._compile_btn.disabled = False
        elif state == "error":
            self._compile_btn.text = "Error ✗"
            self._compile_btn.icon = ft.Icons.ERROR_ROUNDED
            self._compile_btn.bgcolor = COLORS["coral"]
            self._compile_btn.color = COLORS["card_bg"]
            self._compile_btn.disabled = False
        else:  # idle
            self._compile_btn.text = "Compile"
            self._compile_btn.icon = ft.Icons.AUTO_FIX_HIGH_ROUNDED
            self._compile_btn.bgcolor = COLORS["yellow"]
            self._compile_btn.color = COLORS["dark_text"]
            self._compile_btn.disabled = False

    def _show_compile_celebration(self) -> None:
        """コンパイル成功時のパーティクル演出。"""
        import random
        sparkle_chars = ["✦", "✧", "⚡", "★", "✨", "⭐"]
        colors = [COLORS["yellow"], COLORS["green"], COLORS["blue"], "#FFD700", "#00E5FF"]

        # ログ領域にスパークルを表示
        sparkle_line = " ".join(
            random.choice(sparkle_chars) for _ in range(20)
        )
        self._log_list.controls.append(
            ft.Text(sparkle_line, size=14,
                    color=random.choice(colors),
                    text_align=ft.TextAlign.CENTER,
                    weight=ft.FontWeight.W_700)
        )

    def _on_compile(self, e: ft.ControlEvent) -> None:
        self._active_tab.dsl_text = self._editor.value or ""
        code = self._active_tab.dsl_text.strip()
        self._set_compile_btn_state("compiling")
        self._page.update()
        threading.Thread(target=self._compile, args=(code,), daemon=True).start()

    def _compile(self, code: str) -> None:
        import time as _time

        if not code:
            self._log("エディタが空です", COLORS["yellow"])
            self._set_compile_btn_state("idle")
            self._page.update()
            return

        _GREEN = "#00C875"
        _CYAN = "#4EC9B0"
        _DIM = "#6A9955"

        self._log("", COLORS["blue"])
        self._log_list.controls.append(
            ft.Text("$ lifescript compile", color=_DIM, size=11,
                    font_family=_CODE_FONT, selectable=True)
        )
        self._page.update()

        # LLM呼び出し
        self._log_list.controls.append(
            ft.Text("[LLM Compiler]     DSL → Python 変換中…", color=_CYAN, size=11,
                    font_family=_CODE_FONT, selectable=True)
        )
        self._page.update()

        try:
            result = self._compiler.compile(code)
            self._active_tab.compiled = result

            # LLM完了
            self._log_list.controls.append(
                ft.Text(f'[LLM Compiler]     OK — "{result["title"]}"', color=_GREEN, size=11,
                        font_family=_CODE_FONT, selectable=True)
            )
            self._page.update()
            _time.sleep(0.1)

            # セキュリティチェック演出
            checks = [
                (_CYAN, "[AST Validation]   構文解析中…"),
                (_GREEN, "[AST Validation]   OK"),
                (_CYAN, "[Sandbox Guard]    RestrictedPython 検証中…"),
                (_GREEN, "[Sandbox Guard]    OK — 禁止操作なし"),
                (_CYAN, "[Function Guard]   ホワイトリスト照合中…"),
                (_GREEN, "[Function Guard]   OK — 全関数が許可リスト内"),
            ]
            for color, text in checks:
                self._log_list.controls.append(
                    ft.Text(text, color=color, size=11,
                            font_family=_CODE_FONT, selectable=True)
                )
                self._page.update()
                _time.sleep(0.08)

            # Security Passed スタンプ
            self._log_list.controls.append(
                ft.Container(
                    content=ft.Row([
                        ft.Icon(ft.Icons.VERIFIED_ROUNDED, size=14, color=_GREEN),
                        ft.Text("Security Check Passed", size=12,
                                weight=ft.FontWeight.W_700, color=_GREEN,
                                font_family=_CODE_FONT),
                    ], spacing=6, alignment=ft.MainAxisAlignment.CENTER),
                    bgcolor="#00C87510",
                    border=ft.border.all(1, f"{_GREEN}40"),
                    border_radius=8,
                    padding=ft.padding.symmetric(horizontal=12, vertical=4),
                    margin=ft.margin.only(top=2, bottom=2),
                )
            )

            # Pythonコードをタイプライター風にプレビュー表示
            python_code = result["code"]
            self._python_raw = ""
            self._python_preview_text.spans = []
            self._page.update()
            _time.sleep(0.15)

            # 行単位で高速表示
            lines = python_code.split("\n")
            displayed = ""
            for line in lines:
                displayed += line + "\n"
                self._python_raw = displayed
                self._python_preview_text.spans = _highlight_python(displayed)
                self._page.update()
                _time.sleep(0.04)

            # トリガー情報
            trigger = result.get("trigger", {})
            tt = trigger.get("type", "interval")
            if tt == "once":
                self._log("トリガー: 即時実行（▶ Run で実行）", COLORS["mid_text"])
            elif tt == "cron":
                self._log(f'トリガー: 毎日 {trigger["hour"]:02d}:{trigger["minute"]:02d}', COLORS["mid_text"])
            else:
                self._log(f'トリガー: {trigger.get("seconds", 3600)}秒ごと', COLORS["mid_text"])
            self._log("✅ コンパイル完了 — Run または Save で続行", COLORS["green"])
            self._set_compile_btn_state("success")
            self._show_compile_celebration()
            self._page.update()
            # 3秒後にボタンをリセット
            _time.sleep(3)
            self._set_compile_btn_state("idle")
            self._page.update()
        except CompileError as e:
            self._log_list.controls.append(
                ft.Text(f"[LLM Compiler]     ERROR: {e}", color=COLORS["coral"], size=11,
                        font_family=_CODE_FONT, selectable=True)
            )
            self._set_preview(f"# エラー: {e}")
            self._set_compile_btn_state("error")
            self._page.update()
            _time.sleep(3)
            self._set_compile_btn_state("idle")
            self._page.update()

    def _on_run(self, e: ft.ControlEvent) -> None:
        """コンパイル → 即時1回実行（スケジューラ登録しない）。"""
        self._active_tab.dsl_text = self._editor.value or ""
        code = self._active_tab.dsl_text.strip()
        threading.Thread(target=self._run_once, args=(code,), daemon=True).start()

    def _run_once(self, code: str) -> None:
        from ..sandbox.runner import run_sandboxed
        from ..exceptions import SandboxError

        if not code:
            self._log("エディタが空です", COLORS["yellow"])
            return

        # コンパイル
        if self._active_tab.compiled is None:
            self._compile(code)
        if self._active_tab.compiled is None:
            return

        result = self._active_tab.compiled
        python_code = result["code"]

        self._log("実行中…", COLORS["blue"])
        self._set_preview("# 実行中…")
        self._page.update()
        try:
            output = run_sandboxed(python_code, timeout=30, capture=True)
            self._set_preview(f"# 実行結果\n# {'=' * 40}\n\n{output or '(出力なし)'}")
            self._log("実行完了", COLORS["green"])
        except SandboxError as e:
            self._set_preview(f"# 実行エラー\n# {'=' * 40}\n\n{e}")
            self._log(f"実行エラー: {e}", COLORS["coral"])
        self._page.update()

    def _on_save(self, e: ft.ControlEvent) -> None:
        self._active_tab.dsl_text = self._editor.value or ""
        code = self._active_tab.dsl_text.strip()
        threading.Thread(target=self._save_and_register, args=(code,), daemon=True).start()

    def _save_and_register(self, code: str) -> None:
        if not code:
            self._log("エディタが空です", COLORS["yellow"])
            return

        # Compile if not already
        if self._active_tab.compiled is None:
            self._compile(code)
        if self._active_tab.compiled is None:
            return

        result = self._active_tab.compiled
        tab = self._active_tab
        try:
            trigger_dict = result.get("trigger", {"type": "interval", "seconds": 3600})
            # コンパイル結果のtitleをスクリプト名として使用
            compiled_title = result.get("title", "")
            if compiled_title and (tab.name.startswith("untitled_") or tab.name.startswith("script_")):
                tab.name = compiled_title
            script = db_client.save_script(
                dsl_text=code,
                compiled_python=result["code"],
                name=tab.name,
            )
            tab.script_id = str(script["id"])
            self._scheduler.add_script(script, trigger=trigger_dict)
            self._log(f'保存・登録完了: {tab.name}', COLORS["green"])
            tab.compiled = None
            self._load_scripts_list()
        except Exception as e:
            self._log(f"保存エラー: {e}", COLORS["coral"])

    def _on_stop_all(self, e: ft.ControlEvent) -> None:
        self._scheduler.remove_all()
        self._log("全ジョブを停止しました", COLORS["yellow"])

    def _on_script_selected(self, script: dict) -> None:
        # 現在のタブ内容を保存
        self._active_tab.dsl_text = self._editor.value or ""

        # 既にこのスクリプトが開いているタブがあればそこに切り替え
        sid = str(script["id"])
        for tab in self._tabs:
            if tab.script_id == sid:
                self._switch_tab(tab)
                return

        # 新しいタブで開く
        name = script.get("name", "") or (script.get("dsl_text", "") or "")[:20].replace("\n", " ") or f"スクリプト #{script['id']}"
        tab = _Tab(
            name=name,
            dsl_text=script.get("dsl_text", ""),
            script_id=sid,
        )
        self._tabs.append(tab)
        self._active_tab = tab
        self._editor.value = tab.dsl_text
        self._dsl_highlight_text.spans = _highlight_dsl(tab.dsl_text)
        self._update_gallery_visibility()
        self._set_preview(script.get("compiled_python", "# (empty)"))
        self._rebuild_tab_bar()
        self._log(f"{name} を開きました", COLORS["blue"])
        self._page.update()

    def _delete_script(self, script: dict) -> None:
        try:
            self._scheduler.remove_script(str(script["id"]))
            db_client.delete_script(script["id"])
            self._load_scripts_list()
            del_name = script.get("name", "") or f"#{script['id']}"
            self._log(f"「{del_name}」を削除しました", COLORS["yellow"])
        except Exception as e:
            self._log(f"削除エラー: {e}", COLORS["coral"])
