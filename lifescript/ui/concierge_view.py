"""コンシェルジュ画面 — マシンとの汎用チャット。

カレンダー・通知・生活全般についてマシンに相談できる。
即時アクション（予定追加・通知）を実行し、DSLはコピペ用に表示。
"""

from __future__ import annotations

import re
import threading

import flet as ft

from ..chat import ChatEngine
from ..traits import gather_all_traits
from ..database.client import db_client
from .app import (
    BG, CARD_BG, BLUE, GREEN, CORAL, YELLOW, ORANGE, PURPLE,
    DARK_TEXT, MID_TEXT, LIGHT_TEXT, SIDEBAR_BG, darii_image,
)

_BORDER = "#E8E4DC"
_MEMORY_BG = "#FDFCFA"

_WELCOME_MESSAGES = [
    "予定を入れたいときは「〇〇日に〇〇入れて」って言ってね！",
    "カレンダーの内容について聞いてくれてもいいよ。",
    "LifeScript のルールを作りたいときも相談してね！",
]


class ConciergeView:
    def __init__(self, page: ft.Page, model: str | None = None) -> None:
        self._page = page
        self._chat_engine = ChatEngine(model=model)
        self._memory_open = False
        self._chat_messages = ft.ListView(
            expand=True, spacing=8, padding=ft.padding.symmetric(horizontal=16, vertical=8),
            auto_scroll=True,
        )
        self._memory_list = ft.ListView(
            expand=True, spacing=6, padding=ft.padding.symmetric(horizontal=16, vertical=8),
        )
        self._input = ft.TextField(
            hint_text="ダリーに話しかけてね…",
            text_size=14,
            border_radius=24,
            bgcolor=CARD_BG,
            border_color=_BORDER,
            focused_border_color=BLUE,
            content_padding=ft.padding.symmetric(horizontal=20, vertical=14),
            expand=True,
            on_submit=self._on_send,
        )
        self._send_btn = ft.IconButton(
            ft.Icons.SEND_ROUNDED, icon_size=22, icon_color=CARD_BG,
            bgcolor=BLUE, style=ft.ButtonStyle(padding=12, shape=ft.CircleBorder()),
            tooltip="送信",
            on_click=self._on_send,
        )
        # Memory panel controls
        self._memory_btn = ft.IconButton(
            ft.Icons.PSYCHOLOGY_ROUNDED, icon_size=20, icon_color=LIGHT_TEXT,
            tooltip="メモリ（パーソナリティ）",
            style=ft.ButtonStyle(padding=8),
            on_click=self._toggle_memory,
        )
        self._memory_panel = ft.Container(visible=False, expand=True)
        self._chat_area = ft.Container(expand=True)

    def build(self) -> ft.Control:
        # ウェルカムメッセージ
        if not self._chat_messages.controls:
            self._chat_messages.controls.append(self._welcome_bubble())

        header = ft.Container(
            content=ft.Row([
                ft.Container(
                    content=darii_image(36),
                    width=40, height=40, border_radius=12,
                    alignment=ft.Alignment(0, 0),
                ),
                ft.Container(width=10),
                ft.Column([
                    ft.Text("ダリー", size=20, weight=ft.FontWeight.W_800, color=DARK_TEXT),
                    ft.Text("あなたの生活に寄り添うロボット", size=12, color=MID_TEXT),
                ], spacing=1),
                ft.Container(expand=True),
                self._memory_btn,
                ft.IconButton(
                    ft.Icons.REFRESH_ROUNDED, icon_size=20, icon_color=LIGHT_TEXT,
                    tooltip="会話をリセット",
                    style=ft.ButtonStyle(padding=8),
                    on_click=self._on_clear,
                ),
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
            padding=ft.padding.symmetric(horizontal=16, vertical=12),
            border=ft.border.only(bottom=ft.BorderSide(1, _BORDER)),
        )

        input_bar = ft.Container(
            content=ft.Row([
                self._input,
                self._send_btn,
            ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            padding=ft.padding.symmetric(horizontal=16, vertical=12),
            border=ft.border.only(top=ft.BorderSide(1, _BORDER)),
        )

        # Chat area (default visible)
        self._chat_area = ft.Column([
            self._chat_messages,
            input_bar,
        ], expand=True, spacing=0)

        # Memory panel (toggled)
        self._memory_panel = self._build_memory_panel()

        return ft.Container(
            content=ft.Column([
                header,
                ft.Stack([
                    self._chat_area,
                    self._memory_panel,
                ], expand=True),
            ], expand=True, spacing=0),
            expand=True,
            bgcolor=BG,
            border_radius=ft.border_radius.only(top_left=16),
        )

    def receive_logs(self, entries: list) -> None:
        pass  # ログは表示しない

    # ------------------------------------------------------------------
    # Memory panel
    # ------------------------------------------------------------------
    def _build_memory_panel(self) -> ft.Container:
        """メモリパネル: traitsから導出されたパーソナリティを管理。"""
        return ft.Container(
            content=ft.Column([
                # メモリヘッダー
                ft.Container(
                    content=ft.Row([
                        ft.Icon(ft.Icons.PSYCHOLOGY_ROUNDED, size=18, color=BLUE),
                        ft.Text("メモリ", size=16, weight=ft.FontWeight.W_700, color=DARK_TEXT),
                        ft.Container(width=4),
                        ft.Text("ダリーが把握しているあなたの情報", size=11, color=MID_TEXT),
                        ft.Container(expand=True),
                        ft.IconButton(
                            ft.Icons.ADD_ROUNDED, icon_size=18, icon_color=BLUE,
                            tooltip="メモリを追加",
                            style=ft.ButtonStyle(padding=6),
                            on_click=self._on_add_memory,
                        ),
                    ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    padding=ft.padding.symmetric(horizontal=16, vertical=10),
                    border=ft.border.only(bottom=ft.BorderSide(1, _BORDER)),
                ),
                # traits由来の情報表示
                self._memory_list,
            ], expand=True, spacing=0),
            bgcolor=_MEMORY_BG,
            visible=False,
            expand=True,
        )

    def _toggle_memory(self, e: ft.ControlEvent) -> None:
        self._memory_open = not self._memory_open
        self._memory_panel.visible = self._memory_open
        self._chat_area.visible = not self._memory_open
        # ボタンの色を切り替え
        self._memory_btn.icon_color = BLUE if self._memory_open else LIGHT_TEXT
        if self._memory_open:
            self._refresh_memory_list()
        self._page.update()

    def _refresh_memory_list(self) -> None:
        self._memory_list.controls.clear()

        # 1. traits由来のメモリ（読み取り専用表示）
        traits = gather_all_traits()
        if traits:
            self._memory_list.controls.append(ft.Container(
                content=ft.Row([
                    ft.Icon(ft.Icons.AUTO_AWESOME_ROUNDED, size=14, color=PURPLE),
                    ft.Text("Traitsから自動取得", size=11, weight=ft.FontWeight.W_600, color=PURPLE),
                ], spacing=4),
                padding=ft.padding.only(left=4, top=8, bottom=4),
            ))
            for trait in traits:
                self._memory_list.controls.append(self._memory_card(
                    text=trait, source="trait", log_id=None,
                ))

        # 2. マシンの観察（自動メモリ）
        try:
            logs = db_client.get_machine_logs(limit=100)
            memories = [l for l in logs if l.get("action_type") == "memory"]
            auto_memories = [l for l in logs if l.get("action_type") == "memory_auto"]
        except Exception:
            memories = []
            auto_memories = []

        if auto_memories:
            self._memory_list.controls.append(ft.Container(
                content=ft.Row([
                    ft.Icon(ft.Icons.VISIBILITY_ROUNDED, size=14, color=ORANGE),
                    ft.Text("ダリーの観察", size=11, weight=ft.FontWeight.W_600, color=ORANGE),
                ], spacing=4),
                padding=ft.padding.only(left=4, top=12, bottom=4),
            ))
            for mem in auto_memories:
                self._memory_list.controls.append(self._memory_card(
                    text=mem.get("content", ""),
                    source="auto",
                    log_id=mem.get("id"),
                ))

        # 3. ユーザーが手動で追加したメモリ
        if memories:
            self._memory_list.controls.append(ft.Container(
                content=ft.Row([
                    ft.Icon(ft.Icons.EDIT_NOTE_ROUNDED, size=14, color=BLUE),
                    ft.Text("手動で追加", size=11, weight=ft.FontWeight.W_600, color=BLUE),
                ], spacing=4),
                padding=ft.padding.only(left=4, top=12, bottom=4),
            ))
            for mem in memories:
                self._memory_list.controls.append(self._memory_card(
                    text=mem.get("content", ""),
                    source="manual",
                    log_id=mem.get("id"),
                ))

        if not traits and not memories and not auto_memories:
            self._memory_list.controls.append(ft.Container(
                content=ft.Column([
                    ft.Icon(ft.Icons.LIGHTBULB_OUTLINE_ROUNDED, size=32, color=LIGHT_TEXT),
                    ft.Text("メモリはまだありません", size=14, color=MID_TEXT,
                            text_align=ft.TextAlign.CENTER),
                    ft.Text("LifeScript に traits を書くか、\n下の＋ボタンで手動追加できます",
                            size=12, color=LIGHT_TEXT, text_align=ft.TextAlign.CENTER),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=8),
                padding=40, alignment=ft.Alignment(0, 0),
            ))

    def _memory_card(self, text: str, source: str, log_id: int | None) -> ft.Container:
        is_editable = source in ("manual", "auto")
        actions: list[ft.Control] = []
        if is_editable and log_id is not None:
            if source == "manual":
                actions.append(ft.IconButton(
                    ft.Icons.EDIT_ROUNDED, icon_size=14, icon_color=MID_TEXT,
                    tooltip="編集",
                    style=ft.ButtonStyle(padding=4),
                    on_click=lambda e, lid=log_id, t=text: self._on_edit_memory(lid, t),
                ))
            actions.append(ft.IconButton(
                ft.Icons.DELETE_OUTLINE_ROUNDED, icon_size=14, icon_color=CORAL,
                tooltip="削除",
                style=ft.ButtonStyle(padding=4),
                on_click=lambda e, lid=log_id: self._on_delete_memory(lid),
            ))

        icon_map = {
            "trait": (ft.Icons.AUTO_AWESOME_ROUNDED, PURPLE),
            "auto": (ft.Icons.VISIBILITY_ROUNDED, ORANGE),
            "manual": (ft.Icons.PERSON_ROUNDED, BLUE),
        }
        icon, icon_color = icon_map.get(source, (ft.Icons.PERSON_ROUNDED, BLUE))

        return ft.Container(
            content=ft.Row([
                ft.Icon(icon, size=14, color=icon_color),
                ft.Text(text, size=13, color=DARK_TEXT, expand=True),
                *actions,
            ], spacing=6, vertical_alignment=ft.CrossAxisAlignment.START),
            bgcolor=CARD_BG,
            border_radius=10,
            padding=ft.padding.symmetric(horizontal=12, vertical=8),
            border=ft.border.all(1, _BORDER),
        )

    def _on_add_memory(self, e: ft.ControlEvent) -> None:
        tf = ft.TextField(
            hint_text="例: 疲れた時は甘いものが食べたくなる",
            text_size=13, border_radius=8, bgcolor=CARD_BG,
            border_color=_BORDER, focused_border_color=BLUE,
            content_padding=ft.padding.symmetric(horizontal=12, vertical=10),
            multiline=True, min_lines=2, max_lines=4,
        )

        def _save(e: ft.ControlEvent) -> None:
            val = (tf.value or "").strip()
            if not val:
                return
            db_client.add_machine_log(action_type="memory", content=val)
            dlg.open = False
            self._refresh_memory_list()
            self._page.update()

        dlg = ft.AlertDialog(
            title=ft.Text("メモリを追加", size=16, weight=ft.FontWeight.W_700),
            content=ft.Container(content=tf, width=400),
            actions=[
                ft.TextButton("キャンセル", on_click=lambda e: _close()),
                ft.TextButton("追加", on_click=_save,
                              style=ft.ButtonStyle(color=BLUE)),
            ],
        )

        def _close() -> None:
            dlg.open = False
            self._page.update()

        self._page.overlay.append(dlg)
        dlg.open = True
        self._page.update()

    def _on_edit_memory(self, log_id: int, current_text: str) -> None:
        tf = ft.TextField(
            value=current_text,
            text_size=13, border_radius=8, bgcolor=CARD_BG,
            border_color=_BORDER, focused_border_color=BLUE,
            content_padding=ft.padding.symmetric(horizontal=12, vertical=10),
            multiline=True, min_lines=2, max_lines=4,
        )

        def _save(e: ft.ControlEvent) -> None:
            val = (tf.value or "").strip()
            if not val:
                return
            # 削除して再追加（machine_logsにupdate操作がないため）
            db_client.delete_machine_log(log_id)
            db_client.add_machine_log(action_type="memory", content=val)
            dlg.open = False
            self._refresh_memory_list()
            self._page.update()

        dlg = ft.AlertDialog(
            title=ft.Text("メモリを編集", size=16, weight=ft.FontWeight.W_700),
            content=ft.Container(content=tf, width=400),
            actions=[
                ft.TextButton("キャンセル", on_click=lambda e: _close()),
                ft.TextButton("保存", on_click=_save,
                              style=ft.ButtonStyle(color=BLUE)),
            ],
        )

        def _close() -> None:
            dlg.open = False
            self._page.update()

        self._page.overlay.append(dlg)
        dlg.open = True
        self._page.update()

    def _on_delete_memory(self, log_id: int) -> None:
        db_client.delete_machine_log(log_id)
        self._refresh_memory_list()
        self._page.update()

    # ------------------------------------------------------------------
    # Chat logic
    # ------------------------------------------------------------------
    def _on_send(self, e: ft.ControlEvent) -> None:
        msg = (self._input.value or "").strip()
        if not msg:
            return
        self._input.value = ""
        self._chat_messages.controls.append(self._user_bubble(msg))
        loading = self._loading_bubble()
        self._chat_messages.controls.append(loading)
        self._page.update()

        def _call() -> None:
            try:
                reply, actions = self._chat_engine.send(msg)
                if loading in self._chat_messages.controls:
                    self._chat_messages.controls.remove(loading)
                for action in actions:
                    self._chat_messages.controls.append(self._action_bubble(action))
                self._chat_messages.controls.append(self._assistant_bubble(reply))
            except Exception as ex:
                if loading in self._chat_messages.controls:
                    self._chat_messages.controls.remove(loading)
                self._chat_messages.controls.append(self._error_bubble(str(ex)))
            self._page.update()

        threading.Thread(target=_call, daemon=True).start()

    def _on_clear(self, e: ft.ControlEvent) -> None:
        self._chat_engine.clear()
        self._chat_messages.controls.clear()
        self._chat_messages.controls.append(self._welcome_bubble())
        self._page.update()

    # ------------------------------------------------------------------
    # Bubble builders
    # ------------------------------------------------------------------
    def _welcome_bubble(self) -> ft.Container:
        items = [
            ft.Row([
                ft.Container(
                    content=darii_image(28),
                    width=32, height=32, border_radius=10,
                    alignment=ft.Alignment(0, 0),
                ),
                ft.Text("ダリーだよ！なんでも聞いてね！", size=14,
                        weight=ft.FontWeight.W_600, color=DARK_TEXT),
            ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ft.Container(height=4),
        ]
        for msg in _WELCOME_MESSAGES:
            items.append(ft.Container(
                content=ft.Row([
                    ft.Icon(ft.Icons.ARROW_RIGHT_ROUNDED, size=16, color=BLUE),
                    ft.Text(msg, size=13, color=MID_TEXT),
                ], spacing=6),
                padding=ft.padding.only(left=8),
            ))

        return ft.Container(
            content=ft.Column(items, spacing=4),
            bgcolor=f"{BLUE}08",
            border_radius=16,
            padding=16,
            border=ft.border.all(1, f"{BLUE}20"),
            margin=ft.margin.only(right=40),
        )

    def _user_bubble(self, text: str) -> ft.Container:
        return ft.Container(
            content=ft.Text(text, size=14, color=CARD_BG),
            bgcolor=BLUE,
            border_radius=ft.border_radius.only(
                top_left=16, top_right=16, bottom_left=16, bottom_right=4),
            padding=ft.padding.symmetric(horizontal=16, vertical=10),
            margin=ft.margin.only(left=80),
        )

    def _assistant_bubble(self, text: str) -> ft.Container:
        # actionブロック除去
        display = re.sub(r"```action\s*\n?.*?```", "", text, flags=re.DOTALL).strip()

        # lifescriptコードブロックを抽出してコピーボタン付きで表示
        ls_pattern = r"```(?:lifescript|ls)\s*\n?(.*?)```"
        ls_blocks = re.findall(ls_pattern, display, flags=re.DOTALL)
        # lifescriptブロックを除去した残りのMarkdown
        md_text = re.sub(ls_pattern, "", display, flags=re.DOTALL).strip()

        controls: list[ft.Control] = []

        if md_text:
            controls.append(ft.Markdown(
                md_text,
                selectable=True,
                extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
                code_theme=ft.MarkdownCodeTheme.MONOKAI,
                md_style_sheet=ft.MarkdownStyleSheet(
                    p_text_style=ft.TextStyle(size=14, color=DARK_TEXT),
                    h1_text_style=ft.TextStyle(size=20, weight=ft.FontWeight.W_700, color=DARK_TEXT),
                    h2_text_style=ft.TextStyle(size=18, weight=ft.FontWeight.W_700, color=DARK_TEXT),
                    h3_text_style=ft.TextStyle(size=16, weight=ft.FontWeight.W_600, color=DARK_TEXT),
                    strong_text_style=ft.TextStyle(weight=ft.FontWeight.W_700, color=DARK_TEXT),
                    list_bullet_text_style=ft.TextStyle(size=14, color=DARK_TEXT),
                    code_text_style=ft.TextStyle(
                        size=12, color="#E8E4DC",
                        font_family="Courier New, monospace",
                    ),
                ),
            ))

        for code in ls_blocks:
            code = code.strip()
            controls.append(ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Container(
                            content=ft.Text("LifeScript", size=10, color=LIGHT_TEXT,
                                            weight=ft.FontWeight.W_600),
                            padding=ft.padding.symmetric(horizontal=8, vertical=2),
                        ),
                        ft.Container(expand=True),
                        ft.TextButton(
                            "コピー",
                            icon=ft.Icons.COPY_ROUNDED,
                            style=ft.ButtonStyle(
                                color=BLUE, padding=ft.padding.symmetric(horizontal=8),
                                text_style=ft.TextStyle(size=11),
                            ),
                            on_click=lambda e, c=code: self._copy_to_clipboard(c),
                        ),
                    ], spacing=0),
                    ft.Container(
                        content=ft.Text(
                            code, size=12, color="#E8E4DC",
                            font_family="Courier New, monospace",
                            selectable=True,
                        ),
                        bgcolor="#2D2B27",
                        border_radius=8,
                        padding=12,
                    ),
                ], spacing=2),
                border=ft.border.all(1, _BORDER),
                border_radius=10,
            ))

        if not controls:
            controls.append(ft.Text(display or "…", size=14, color=DARK_TEXT))

        return ft.Container(
            content=ft.Column(controls, spacing=8),
            bgcolor=CARD_BG,
            border_radius=ft.border_radius.only(
                top_left=16, top_right=16, bottom_left=4, bottom_right=16),
            padding=ft.padding.symmetric(horizontal=16, vertical=10),
            margin=ft.margin.only(right=40),
            border=ft.border.all(1, _BORDER),
        )

    def _action_bubble(self, action: dict) -> ft.Container:
        success = action.get("success", False)
        desc = action.get("description", "")
        icon = ft.Icons.CHECK_CIRCLE_ROUNDED if success else ft.Icons.ERROR_ROUNDED
        color = GREEN if success else CORAL
        bg = "#F0FFF0" if success else "#FFF0F0"

        return ft.Container(
            content=ft.Row([
                ft.Icon(icon, size=18, color=color),
                ft.Text(desc, size=13, color=DARK_TEXT, expand=True,
                        weight=ft.FontWeight.W_500),
            ], spacing=8),
            bgcolor=bg,
            border_radius=12,
            padding=ft.padding.symmetric(horizontal=14, vertical=8),
            border=ft.border.all(1, color),
            margin=ft.margin.only(right=40),
        )

    def _loading_bubble(self) -> ft.Container:
        return ft.Container(
            content=ft.Row([
                ft.ProgressRing(width=16, height=16, stroke_width=2, color=BLUE),
                ft.Text("考え中…", size=13, color=LIGHT_TEXT),
            ], spacing=8),
            padding=ft.padding.symmetric(horizontal=16, vertical=10),
            margin=ft.margin.only(right=40),
        )

    def _error_bubble(self, msg: str) -> ft.Container:
        return ft.Container(
            content=ft.Row([
                ft.Icon(ft.Icons.ERROR_OUTLINE_ROUNDED, size=18, color=CORAL),
                ft.Text(f"エラー: {msg}", size=13, color=CORAL, expand=True),
            ], spacing=8),
            bgcolor="#FFF0F0",
            border_radius=12,
            padding=ft.padding.symmetric(horizontal=14, vertical=8),
            border=ft.border.all(1, CORAL),
        )

    def _copy_to_clipboard(self, text: str) -> None:
        self._page.set_clipboard(text)
        self._page.update()
