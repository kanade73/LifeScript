"""IDE画面 — DSL記述・コンパイル・スケジューラ登録の中核。

- DSLテキストエディタ
- コンパイルボタン
- 生成Pythonコードのプレビュー
- スケジューラへの登録ボタン
- エラー・警告表示
"""

from __future__ import annotations

import threading

import flet as ft

from ..compiler.compiler import Compiler
from ..database.client import db_client
from ..exceptions import CompileError
from .app import COLORS

_DEFAULT_DSL = """\
# 例: バイトが週4以上なら回復タイムを提案
when calendar.read("バイト").count_this_week >= 4:
  calendar.suggest("回復タイム", on="next_free_morning")

# 例: 毎日のリマインド
every day:
  notify("今日も頑張ろう！")
"""


class EditorView:
    def __init__(self, page: ft.Page, compiler: Compiler, scheduler) -> None:
        self._page = page
        self._compiler = compiler
        self._scheduler = scheduler
        self._last_compiled: dict | None = None
        self._loaded_script_id: str | None = None

        # ── DSL Editor ────────────────────────────────────────
        self._editor = ft.TextField(
            value=_DEFAULT_DSL,
            multiline=True,
            min_lines=16,
            expand=True,
            text_style=ft.TextStyle(
                font_family="Courier New, monospace",
                size=13, color=COLORS["editor_fg"],
            ),
            bgcolor=COLORS["editor_bg"],
            border_color=ft.Colors.TRANSPARENT,
            focused_border_color=COLORS["yellow"],
            border_radius=12,
            cursor_color=COLORS["yellow"],
            hint_text="LifeScript DSL を入力…",
            hint_style=ft.TextStyle(color=COLORS["light_text"]),
            content_padding=ft.padding.all(16),
        )

        editor_panel = ft.Container(
            content=ft.Column([
                ft.Container(
                    content=ft.Row([
                        ft.Container(
                            content=ft.Row([
                                ft.Icon(ft.Icons.DESCRIPTION_ROUNDED, size=14, color=COLORS["yellow"]),
                                ft.Text("script.ls", size=12, weight=ft.FontWeight.W_600, color=COLORS["dark_text"]),
                            ], spacing=6),
                            bgcolor=COLORS["card_bg"],
                            border_radius=ft.border_radius.only(top_left=10, top_right=10),
                            padding=ft.padding.symmetric(horizontal=14, vertical=8),
                            border=ft.border.only(bottom=ft.BorderSide(2, COLORS["yellow"])),
                        ),
                    ], spacing=2),
                    padding=ft.padding.only(left=4, bottom=0),
                ),
                self._editor,
            ], spacing=0, expand=True),
            expand=2,
            border_radius=16,
            bgcolor=COLORS["editor_bg"],
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        )

        # ── Python preview ────────────────────────────────────
        self._python_preview = ft.TextField(
            value="# コンパイル結果がここに表示されます",
            multiline=True,
            min_lines=16,
            expand=True,
            read_only=True,
            text_style=ft.TextStyle(
                font_family="Courier New, monospace",
                size=12, color="#A8D8A8",
            ),
            bgcolor="#1E1C19",
            border_color=ft.Colors.TRANSPARENT,
            border_radius=12,
            content_padding=ft.padding.all(16),
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
                self._python_preview,
            ], spacing=0, expand=True),
            expand=1,
            border_radius=16,
            bgcolor="#1E1C19",
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        )

        # ── Scripts list (sidebar) ────────────────────────────
        self._scripts_list = ft.ListView(expand=True, spacing=4, padding=4)

        sidebar = ft.Container(
            content=ft.Column([
                ft.Container(
                    content=ft.Row([
                        ft.Icon(ft.Icons.BOLT_ROUNDED, size=16, color=COLORS["yellow"]),
                        ft.Text("Scripts", size=13, weight=ft.FontWeight.W_700, color=COLORS["dark_text"]),
                    ], spacing=6),
                    padding=ft.padding.only(left=8, top=4, bottom=4),
                ),
                self._scripts_list,
            ], expand=True, spacing=8),
            width=200,
            bgcolor=COLORS["card_bg"],
            border_radius=16,
            padding=12,
            border=ft.border.all(1, "#E8E4DC"),
        )

        # ── Function reference ────────────────────────────────
        from ..functions import FUNCTION_DESCRIPTIONS
        ref_items = []
        for f in FUNCTION_DESCRIPTIONS:
            ref_items.append(
                ft.Container(
                    content=ft.Column([
                        ft.Text(f["name"], size=12, weight=ft.FontWeight.W_600, color=COLORS["blue"]),
                        ft.Text(f["signature"], size=10, color=COLORS["mid_text"], font_family="Courier New"),
                        ft.Text(f["description"], size=10, color=COLORS["light_text"]),
                    ], spacing=2),
                    padding=ft.padding.only(bottom=8),
                )
            )

        # ── Action toolbar ────────────────────────────────────
        action_bar = ft.Container(
            content=ft.Row([
                ft.ElevatedButton(
                    "Compile",
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
                    "Save & Register",
                    icon=ft.Icons.SAVE_ROUNDED,
                    bgcolor=COLORS["green"],
                    color=COLORS["card_bg"],
                    style=ft.ButtonStyle(
                        shape=ft.RoundedRectangleBorder(radius=12),
                        elevation=0,
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
                        shape=ft.RoundedRectangleBorder(radius=12),
                        elevation=0,
                        padding=ft.padding.symmetric(horizontal=20, vertical=12),
                    ),
                    on_click=self._on_stop_all,
                ),
                ft.Container(expand=True),
                # Snippet buttons
                ft.OutlinedButton(
                    "when", style=ft.ButtonStyle(
                        shape=ft.RoundedRectangleBorder(radius=10),
                        side=ft.BorderSide(1, COLORS["green"]),
                        color=COLORS["green"],
                        padding=ft.padding.symmetric(horizontal=14, vertical=10),
                    ),
                    on_click=lambda e: self._insert_snippet('when calendar.read("").count_this_week >= 0:\n  '),
                ),
                ft.OutlinedButton(
                    "notify", style=ft.ButtonStyle(
                        shape=ft.RoundedRectangleBorder(radius=10),
                        side=ft.BorderSide(1, COLORS["coral"]),
                        color=COLORS["coral"],
                        padding=ft.padding.symmetric(horizontal=14, vertical=10),
                    ),
                    on_click=lambda e: self._insert_snippet('notify("")'),
                ),
                ft.OutlinedButton(
                    "calendar", style=ft.ButtonStyle(
                        shape=ft.RoundedRectangleBorder(radius=10),
                        side=ft.BorderSide(1, COLORS["blue"]),
                        color=COLORS["blue"],
                        padding=ft.padding.symmetric(horizontal=14, vertical=10),
                    ),
                    on_click=lambda e: self._insert_snippet('calendar.add("", start="")'),
                ),
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
            border_radius=16,
            padding=12,
            border=ft.border.all(1, "#E8E4DC"),
        )

        self._ref_items = ref_items

        self._content = ft.Column([
            ft.Row([
                ft.Column([editor_panel, preview_panel], expand=3, spacing=8),
                sidebar,
            ], expand=True, spacing=12),
            action_bar,
            log_panel,
        ], expand=True, spacing=10)

        self._load_scripts_list()

    def build(self) -> ft.Column:
        return self._content

    def _insert_snippet(self, snippet: str) -> None:
        current = self._editor.value or ""
        if current and not current.endswith("\n"):
            current += "\n"
        self._editor.value = current + snippet
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
                ft.Text(text, color=color, size=11, font_family="Courier New, monospace", selectable=True)
            )
        if len(self._log_list.controls) > 300:
            self._log_list.controls = self._log_list.controls[-300:]
        self._page.update()

    def _log(self, msg: str, color: str) -> None:
        self._log_list.controls.append(
            ft.Text(msg, color=color, size=11, font_family="Courier New, monospace", selectable=True)
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
        dsl_preview = (script.get("dsl_text", "") or "")[:40].replace("\n", " ")
        return ft.Container(
            content=ft.Row([
                ft.Container(width=8, height=8, border_radius=4, bgcolor=COLORS["green"]),
                ft.Text(
                    f"#{script['id']} {dsl_preview}",
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
    def _on_compile(self, e: ft.ControlEvent) -> None:
        code = (self._editor.value or "").strip()
        threading.Thread(target=self._compile, args=(code,), daemon=True).start()

    def _compile(self, code: str) -> None:
        if not code:
            self._log("エディタが空です", COLORS["yellow"])
            return
        self._log("コンパイル中…", COLORS["blue"])
        try:
            result = self._compiler.compile(code)
            self._last_compiled = result
            self._python_preview.value = result["code"]
            self._log(f'コンパイル完了: "{result["title"]}"', COLORS["green"])
            trigger = result.get("trigger", {})
            if trigger.get("type") == "cron":
                self._log(f'トリガー: 毎日 {trigger["hour"]:02d}:{trigger["minute"]:02d}', COLORS["mid_text"])
            else:
                self._log(f'トリガー: {trigger.get("seconds", 3600)}秒ごと', COLORS["mid_text"])
            self._page.update()
        except CompileError as e:
            self._log(f"コンパイルエラー: {e}", COLORS["coral"])
            self._python_preview.value = f"# エラー: {e}"
            self._page.update()

    def _on_save(self, e: ft.ControlEvent) -> None:
        code = (self._editor.value or "").strip()
        threading.Thread(target=self._save_and_register, args=(code,), daemon=True).start()

    def _save_and_register(self, code: str) -> None:
        if not code:
            self._log("エディタが空です", COLORS["yellow"])
            return

        # Compile if not already
        if self._last_compiled is None:
            self._compile(code)
        if self._last_compiled is None:
            return

        result = self._last_compiled
        try:
            trigger_dict = result.get("trigger", {"type": "interval", "seconds": 3600})
            script = db_client.save_script(
                dsl_text=code,
                compiled_python=result["code"],
            )
            self._scheduler.add_script(script, trigger=trigger_dict)
            self._log(f'保存・登録完了: Script#{script["id"]}', COLORS["green"])
            self._last_compiled = None
            self._load_scripts_list()
        except Exception as e:
            self._log(f"保存エラー: {e}", COLORS["coral"])

    def _on_stop_all(self, e: ft.ControlEvent) -> None:
        self._scheduler.remove_all()
        self._log("全ジョブを停止しました", COLORS["yellow"])

    def _on_script_selected(self, script: dict) -> None:
        self._editor.value = script.get("dsl_text", "")
        self._python_preview.value = script.get("compiled_python", "# (empty)")
        self._loaded_script_id = str(script["id"])
        self._log(f"Script#{script['id']} を読み込みました", COLORS["blue"])
        self._page.update()

    def _delete_script(self, script: dict) -> None:
        try:
            self._scheduler.remove_script(str(script["id"]))
            db_client.delete_script(script["id"])
            self._load_scripts_list()
            self._log(f"Script#{script['id']} を削除しました", COLORS["yellow"])
        except Exception as e:
            self._log(f"削除エラー: {e}", COLORS["coral"])
