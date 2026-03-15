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
            on_change=self._on_editor_change,
        )
        self._prev_editor_value = _DEFAULT_DSL

        # ── タブバー ──────────────────────────────────────────
        self._tab_bar = ft.Row(spacing=2, scroll=ft.ScrollMode.AUTO)

        self._editor_panel = ft.Container(
            content=ft.Column([
                ft.Container(
                    content=self._tab_bar,
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
            border=ft.border.all(1, _BORDER),
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
            border=ft.border.all(1, _BORDER),
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

        self._rebuild_tab_bar()
        self._load_scripts_list()

    def build(self) -> ft.Column:
        self._setup_tab_key()
        return self._content

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

    def _on_editor_change(self, e: ft.ControlEvent) -> None:
        """改行時に自動インデント: 前の行が `:` で終わっていれば2スペース追加。"""
        val = self._editor.value or ""
        prev = self._prev_editor_value or ""
        self._prev_editor_value = val

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
        compiled = tab.compiled
        if compiled:
            self._python_preview.value = compiled.get("code", "")
        else:
            self._python_preview.value = "# コンパイル結果がここに表示されます"
        self._rebuild_tab_bar()
        self._page.update()

    def _new_tab(self) -> None:
        self._active_tab.dsl_text = self._editor.value or ""
        tab = _Tab()
        self._tabs.append(tab)
        self._active_tab = tab
        self._editor.value = ""
        self._python_preview.value = "# コンパイル結果がここに表示されます"
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
            compiled = self._active_tab.compiled
            self._python_preview.value = compiled.get("code", "") if compiled else "# コンパイル結果がここに表示されます"
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
        name = script.get("name", "") or ""
        dsl_preview = (script.get("dsl_text", "") or "")[:30].replace("\n", " ")
        display = name if name else f"#{script['id']} {dsl_preview}"
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
    def _on_compile(self, e: ft.ControlEvent) -> None:
        self._active_tab.dsl_text = self._editor.value or ""
        code = self._active_tab.dsl_text.strip()
        threading.Thread(target=self._compile, args=(code,), daemon=True).start()

    def _compile(self, code: str) -> None:
        if not code:
            self._log("エディタが空です", COLORS["yellow"])
            return
        self._log("コンパイル中…", COLORS["blue"])
        try:
            result = self._compiler.compile(code)
            self._active_tab.compiled = result
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
            script = db_client.save_script(
                dsl_text=code,
                compiled_python=result["code"],
                name=tab.name,
            )
            tab.script_id = str(script["id"])
            self._scheduler.add_script(script, trigger=trigger_dict)
            self._log(f'保存・登録完了: {tab.name} (#{script["id"]})', COLORS["green"])
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
        name = script.get("name", "") or f"script_{script['id']}.ls"
        tab = _Tab(
            name=name,
            dsl_text=script.get("dsl_text", ""),
            script_id=sid,
        )
        self._tabs.append(tab)
        self._active_tab = tab
        self._editor.value = tab.dsl_text
        self._python_preview.value = script.get("compiled_python", "# (empty)")
        self._rebuild_tab_bar()
        self._log(f"{name} を開きました", COLORS["blue"])
        self._page.update()

    def _delete_script(self, script: dict) -> None:
        try:
            self._scheduler.remove_script(str(script["id"]))
            db_client.delete_script(script["id"])
            self._load_scripts_list()
            self._log(f"Script#{script['id']} を削除しました", COLORS["yellow"])
        except Exception as e:
            self._log(f"削除エラー: {e}", COLORS["coral"])
