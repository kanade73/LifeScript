"""エディタ画面 — Miro 風デザイン + VSCode 風コードエディタ。

LifeScript コードの記述・コンパイル・ルール保存を行うメイン作業画面。
"""

from __future__ import annotations

import threading

import flet as ft

from ..compiler.compiler import Compiler
from ..database.client import db_client
from ..exceptions import CompileError
from .app import COLORS

_DEFAULT_CODE = """\
// 例: 毎朝8時にログ記録
every day {
  when fetch(time.now) == "08:00" {
    log("おはようございます")
  }
}
"""


class EditorView:
    def __init__(self, page: ft.Page, compiler: Compiler, scheduler) -> None:
        self._page = page
        self._compiler = compiler
        self._scheduler = scheduler
        self._loaded_rule_id: str | None = None

        # ── Code Editor ─────────────────────────────────────────────
        self._editor = ft.TextField(
            value=_DEFAULT_CODE,
            multiline=True,
            min_lines=18,
            expand=True,
            text_style=ft.TextStyle(
                font_family="Courier New, monospace",
                size=13,
                color=COLORS["editor_fg"],
            ),
            bgcolor=COLORS["editor_bg"],
            border_color=ft.Colors.TRANSPARENT,
            focused_border_color=COLORS["yellow"],
            border_radius=12,
            cursor_color=COLORS["yellow"],
            hint_text="LifeScript code here…",
            hint_style=ft.TextStyle(color=COLORS["light_text"]),
            content_padding=ft.padding.all(16),
        )

        editor_panel = ft.Container(
            content=ft.Column(
                [
                    # Tab bar
                    ft.Container(
                        content=ft.Row(
                            [
                                ft.Container(
                                    content=ft.Row(
                                        [
                                            ft.Icon(
                                                ft.Icons.DESCRIPTION_ROUNDED,
                                                size=14,
                                                color=COLORS["yellow"],
                                            ),
                                            ft.Text(
                                                "main.ls",
                                                size=12,
                                                weight=ft.FontWeight.W_600,
                                                color=COLORS["dark_text"],
                                            ),
                                        ],
                                        spacing=6,
                                    ),
                                    bgcolor=COLORS["card_bg"],
                                    border_radius=ft.border_radius.only(top_left=10, top_right=10),
                                    padding=ft.padding.symmetric(horizontal=14, vertical=8),
                                    border=ft.border.only(
                                        bottom=ft.BorderSide(2, COLORS["yellow"])
                                    ),
                                ),
                            ],
                            spacing=2,
                        ),
                        padding=ft.padding.only(left=4, bottom=0),
                    ),
                    # Editor
                    self._editor,
                ],
                spacing=0,
                expand=True,
            ),
            expand=2,
            border_radius=16,
            bgcolor=COLORS["editor_bg"],
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        )

        # ── Sidebar: Active Rules ───────────────────────────────────
        self._rules_list = ft.ListView(expand=True, spacing=4, padding=4)

        sidebar = ft.Container(
            content=ft.Column(
                [
                    ft.Container(
                        content=ft.Row(
                            [
                                ft.Icon(
                                    ft.Icons.BOLT_ROUNDED,
                                    size=16,
                                    color=COLORS["yellow"],
                                ),
                                ft.Text(
                                    "Active Rules",
                                    size=13,
                                    weight=ft.FontWeight.W_700,
                                    color=COLORS["dark_text"],
                                ),
                            ],
                            spacing=6,
                        ),
                        padding=ft.padding.only(left=8, top=4, bottom=4),
                    ),
                    self._rules_list,
                ],
                expand=True,
                spacing=8,
            ),
            expand=1,
            bgcolor=COLORS["card_bg"],
            border_radius=16,
            padding=12,
            border=ft.border.all(1, "#E8E4DC"),
        )

        # ── Action toolbar ──────────────────────────────────────────
        action_bar = ft.Container(
            content=ft.Row(
                [
                    ft.ElevatedButton(
                        "Compile & Save",
                        icon=ft.Icons.AUTO_FIX_HIGH_ROUNDED,
                        bgcolor=COLORS["yellow"],
                        color=COLORS["dark_text"],
                        style=ft.ButtonStyle(
                            shape=ft.RoundedRectangleBorder(radius=12),
                            elevation=0,
                            padding=ft.padding.symmetric(horizontal=20, vertical=12),
                        ),
                        on_click=self._on_compile,
                    ),
                    ft.ElevatedButton(
                        "Run All",
                        icon=ft.Icons.PLAY_ARROW_ROUNDED,
                        bgcolor=COLORS["green"],
                        color=COLORS["card_bg"],
                        style=ft.ButtonStyle(
                            shape=ft.RoundedRectangleBorder(radius=12),
                            elevation=0,
                            padding=ft.padding.symmetric(horizontal=20, vertical=12),
                        ),
                        on_click=self._on_run_all,
                    ),
                    ft.ElevatedButton(
                        "Stop All",
                        icon=ft.Icons.STOP_ROUNDED,
                        bgcolor=COLORS["coral"],
                        color=COLORS["card_bg"],
                        style=ft.ButtonStyle(
                            shape=ft.RoundedRectangleBorder(radius=12),
                            elevation=0,
                            padding=ft.padding.symmetric(horizontal=20, vertical=12),
                        ),
                        on_click=self._on_stop_all,
                    ),
                    ft.OutlinedButton(
                        "every",
                        style=ft.ButtonStyle(
                            shape=ft.RoundedRectangleBorder(radius=10),
                            side=ft.BorderSide(1, COLORS["blue"]),
                            color=COLORS["blue"],
                            padding=ft.padding.symmetric(horizontal=14, vertical=10),
                        ),
                        on_click=lambda e: self._insert_snippet('every 1h {\n  \n}'),
                    ),
                    ft.OutlinedButton(
                        "when",
                        style=ft.ButtonStyle(
                            shape=ft.RoundedRectangleBorder(radius=10),
                            side=ft.BorderSide(1, COLORS["green"]),
                            color=COLORS["green"],
                            padding=ft.padding.symmetric(horizontal=14, vertical=10),
                        ),
                        on_click=lambda e: self._insert_snippet('when fetch(time.now) == "08:00" {\n \n}'),
                    ),
                    ft.OutlinedButton(
                        "log",
                        style=ft.ButtonStyle(
                            shape=ft.RoundedRectangleBorder(radius=10),
                            side=ft.BorderSide(1, COLORS["coral"]),
                            color=COLORS["coral"],
                            padding=ft.padding.symmetric(horizontal=14, vertical=10),
                        ),
                        #ここのlog()の中身を変更
                        on_click=lambda e: self._insert_snippet('log("表示したい内容をここへ")'),
                    ),
                    ft.OutlinedButton(
                        "fetch",
                        style=ft.ButtonStyle(
                            shape=ft.RoundedRectangleBorder(radius=10),
                            side=ft.BorderSide(1, COLORS["orange"]),
                            color=COLORS["orange"],
                            padding=ft.padding.symmetric(horizontal=14, vertical=10),
                        ),
                        on_click=lambda e: self._insert_snippet('fetch(time.now)'),
                    ),
                    ft.OutlinedButton(
                        "if",
                        style=ft.ButtonStyle(
                            shape=ft.RoundedRectangleBorder(radius=10),
                            side=ft.BorderSide(1, COLORS["brown"]),
                            color=COLORS["brown"],
                            padding=ft.padding.symmetric(horizontal=14, vertical=10),
                        ),
                        on_click=lambda e: self._insert_snippet('if 条件 {\n \n}'),
                    ),
                    ft.OutlinedButton(
                        "let",
                        style=ft.ButtonStyle(
                            shape=ft.RoundedRectangleBorder(radius=10),
                            side=ft.BorderSide(1, COLORS["purple"]),
                            color=COLORS["purple"],
                            padding=ft.padding.symmetric(horizontal=14, vertical=10),
                        ),
                        on_click=lambda e: self._insert_snippet('let x ='),
                    ),
                ],
                spacing=10,
            ),
            padding=ft.padding.symmetric(vertical=4),
        )

        # ── Log panel (terminal-like) ───────────────────────────────
        self._log_list = ft.ListView(expand=True, auto_scroll=True, spacing=1)

        log_panel = ft.Container(
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Icon(
                                ft.Icons.TERMINAL_ROUNDED,
                                size=14,
                                color=COLORS["light_text"],
                            ),
                            ft.Text(
                                "Output",
                                size=12,
                                weight=ft.FontWeight.W_600,
                                color=COLORS["mid_text"],
                            ),
                        ],
                        spacing=6,
                    ),
                    ft.Container(
                        content=self._log_list,
                        expand=True,
                        bgcolor=COLORS["editor_bg"],
                        border_radius=10,
                        padding=10,
                    ),
                ],
                spacing=6,
                expand=True,
            ),
            height=160,
            bgcolor=COLORS["card_bg"],
            border_radius=16,
            padding=12,
            border=ft.border.all(1, "#E8E4DC"),
        )

        # ── Main layout ────────────────────────────────────────────
        self._content = ft.Column(
            [
                ft.Row([editor_panel, sidebar], expand=True, spacing=12),
                action_bar,
                log_panel,
            ],
            expand=True,
            spacing=10,
        )

        self._load_rules_list()

    def build(self) -> ft.Column:
        return self._content

    def _insert_snippet(self, snippet: str) -> None:
        current = self._editor.value or ""
        if current and not current.endswith("\n"):
            current += "\n"
        self._editor.value = current + snippet
        self._page.update()

    # ------------------------------------------------------------------
    # Log receiving (called by AppController)
    # ------------------------------------------------------------------
    def receive_logs(self, entries: list[str]) -> None:
        for entry in entries:
            color = self._log_color(entry)
            self._log_list.controls.append(
                ft.Text(
                    entry,
                    color=color,
                    size=11,
                    font_family="Courier New, monospace",
                    selectable=True,
                )
            )
        self._trim_logs()
        self._page.update()

    # ------------------------------------------------------------------
    # Logging helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _log_color(text: str) -> str:
        if "ERROR" in text:
            return COLORS["coral"]
        if "WARN" in text:
            return COLORS["yellow"]
        return COLORS["green"]

    def _append_log(self, text: str, color: str) -> None:
        self._log_list.controls.append(
            ft.Text(
                text,
                color=color,
                size=11,
                font_family="Courier New, monospace",
                selectable=True,
            )
        )
        self._trim_logs()
        self._page.update()

    def _trim_logs(self) -> None:
        if len(self._log_list.controls) > 300:
            self._log_list.controls = self._log_list.controls[-300:]

    def _log_info(self, msg: str) -> None:
        self._append_log(msg, COLORS["green"])

    def _log_warn(self, msg: str) -> None:
        self._append_log(msg, COLORS["yellow"])

    def _log_error(self, msg: str) -> None:
        self._append_log(msg, COLORS["coral"])

    def _log_cyan(self, msg: str) -> None:
        self._append_log(msg, COLORS["blue"])

    # ------------------------------------------------------------------
    # Rules list
    # ------------------------------------------------------------------
    def _load_rules_list(self) -> None:
        self._rules_list.controls.clear()
        try:
            rules = db_client.get_rules()
            if not rules:
                self._rules_list.controls.append(
                    ft.Container(
                        content=ft.Text(
                            "No rules yet — write some LifeScript!",
                            size=12,
                            color=COLORS["light_text"],
                            italic=True,
                        ),
                        padding=ft.padding.all(8),
                    )
                )
            for rule in rules:
                self._rules_list.controls.append(self._rule_tile(rule))
        except Exception as e:
            self._log_error(f"Failed to load rules: {e}")
        self._page.update()

    def _rule_tile(self, rule: dict) -> ft.Container:
        return ft.Container(
            content=ft.Row(
                [
                    ft.Container(
                        width=8,
                        height=8,
                        border_radius=4,
                        bgcolor=COLORS["green"],
                    ),
                    ft.Text(
                        rule.get("title", "untitled"),
                        size=12,
                        weight=ft.FontWeight.W_500,
                        color=COLORS["dark_text"],
                        expand=True,
                    ),
                    ft.IconButton(
                        icon=ft.Icons.CLOSE_ROUNDED,
                        icon_color=COLORS["light_text"],
                        icon_size=14,
                        tooltip="Delete",
                        style=ft.ButtonStyle(padding=4),
                        on_click=lambda e, r=rule: threading.Thread(
                            target=self._delete_rule, args=(r,), daemon=True
                        ).start(),
                    ),
                ],
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            bgcolor=COLORS["bg"],
            border_radius=10,
            padding=ft.padding.symmetric(horizontal=10, vertical=6),
            on_click=lambda e, r=rule: self._on_rule_selected(r),
            ink=True,
        )

    # ------------------------------------------------------------------
    # Button handlers
    # ------------------------------------------------------------------
    def _on_compile(self, e) -> None:
        code = (self._editor.value or "").strip()
        threading.Thread(target=self._compile_and_save, args=(code,), daemon=True).start()

    def _compile_and_save(self, code: str) -> None:
        if not code:
            self._log_warn("Editor is empty.")
            return
        self._log_cyan("コンパイル中…")
        try:
            result = self._compiler.compile(code)
        except CompileError as e:
            self._log_error(f"コンパイルエラー: {e}")
            return
        try:
            trigger = result["trigger"]
            trigger_seconds = int(trigger.get("seconds", 60))

            rule = db_client.save_rule(
                title=result["title"],
                lifescript_code=code,
                compiled_python=result["code"],
                trigger_seconds=trigger_seconds,
            )
            self._scheduler.add_rule(rule)
            self._log_info(f'コンパイル完了: "{result["title"]}"')
            self._load_rules_list()
        except Exception as e:
            self._log_error(f"保存エラー: {e}")

    def _on_run_all(self, e) -> None:
        if not self._scheduler.is_running:
            self._scheduler.start()
            self._log_info("Scheduler started.")
        else:
            self._log_warn("Scheduler is already running.")

    def _on_stop_all(self, e) -> None:
        self._scheduler.remove_all()
        self._log_warn("All jobs stopped.")

    def _on_rule_selected(self, rule: dict) -> None:
        self._editor.value = rule.get("lifescript_code", "")
        self._loaded_rule_id = str(rule["id"])
        self._log_cyan(f"Loaded rule: {rule.get('title')}")
        self._page.update()

    def _delete_rule(self, rule: dict) -> None:
        try:
            self._scheduler.remove_rule(rule["id"])
            db_client.delete_rule(rule["id"])
            self._load_rules_list()
            self._log_warn("Rule deleted.")
        except Exception as e:
            self._log_error(f"Delete error: {e}")
