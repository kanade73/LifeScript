"""Flet アプリケーションのエントリポイント — Miro 風ポップデザイン + VSCode 風構造。

全画面（Home / Editor / Dashboard）のナビゲーション、ログポーリング、
ステータスバーを管理するアプリの骨格。
"""

from __future__ import annotations

import threading

import flet as ft

from ..compiler.compiler import Compiler
from ..database.client import db_client
from ..scheduler.scheduler import LifeScriptScheduler
from .. import log_queue

#ボタンの実装のために色を追加定義
# ── Miro-inspired colour palette ────────────────────────────────────
BG = "#FAFAF8"
SIDEBAR_BG = "#F0EDE6"
CARD_BG = "#FFFFFF"
EDITOR_BG = "#2D2B27"
EDITOR_FG = "#E8E4DC"
YELLOW = "#FFD02F"
ORANGE = "#FFA500"
BROWN = "#DC8551"
BLUE = "#4262FF"
GREEN = "#00C875"
CORAL = "#FF7575"
PURPLE = "#9B59B6"
DARK_TEXT = "#2D2B27"
MID_TEXT = "#6B6560"
LIGHT_TEXT = "#A09A93"

#色の名前？の定義も追加
# Re-export for use by other modules
COLORS = {
    "bg": BG,
    "sidebar_bg": SIDEBAR_BG,
    "card_bg": CARD_BG,
    "editor_bg": EDITOR_BG,
    "editor_fg": EDITOR_FG,
    "yellow": YELLOW,
    "blue": BLUE,
    "green": GREEN,
    "coral": CORAL,
    "purple": PURPLE,
    "orange": ORANGE,
    "brown": BROWN,
    "dark_text": DARK_TEXT,
    "mid_text": MID_TEXT,
    "light_text": LIGHT_TEXT,
}


def create_app(compiler: Compiler, scheduler: LifeScriptScheduler):
    """コンパイラとスケジューラを束縛した Flet メイン関数を返す。"""

    def main(page: ft.Page) -> None:
        page.title = "LifeScript"
        page.bgcolor = BG
        page.theme_mode = ft.ThemeMode.LIGHT
        page.theme = ft.Theme(
            color_scheme_seed=ft.Colors.AMBER,
            use_material3=True,
            visual_density=ft.VisualDensity.COMPACT,
        )
        page.window.width = 1100
        page.window.height = 760
        page.window.min_width = 800
        page.window.min_height = 600
        page.padding = 0

        from .home_view import HomeView  # noqa: PLC0415
        from .main_screen import EditorView  # noqa: PLC0415
        from .dashboard_view import DashboardView  # noqa: PLC0415
        from .settings_screen import SettingsDialog  # noqa: PLC0415

        # ── DB connect (Supabase or SQLite fallback) ──────────────
        db_client.connect()
        if db_client.is_connected and not scheduler.is_running:
            scheduler.start()
            scheduler.load_from_db()

        home_view = HomeView(page=page, scheduler=scheduler)
        editor_view = EditorView(page=page, compiler=compiler, scheduler=scheduler)
        dashboard_view = DashboardView(page=page, scheduler=scheduler)

        views = [home_view, editor_view, dashboard_view]
        active_view: list = [home_view]

        # ── Content area ────────────────────────────────────────────
        content_area = ft.Container(
            content=home_view.build(),
            expand=True,
            bgcolor=BG,
            padding=ft.padding.only(top=8, left=8, right=8, bottom=0),
            border_radius=ft.border_radius.only(top_left=16),
        )

        # ── Activity bar navigation ─────────────────────────────────
        def _on_nav(index: int) -> None:
            active_view[0] = views[index]
            content_area.content = views[index].build()
            for i, btn in enumerate(nav_buttons):
                btn.style = ft.ButtonStyle(
                    bgcolor=YELLOW if i == index else ft.Colors.TRANSPARENT,
                    shape=ft.RoundedRectangleBorder(radius=12),
                    padding=12,
                )
            page.update()

        nav_buttons = [
            ft.IconButton(
                icon=ft.Icons.HOME_ROUNDED,
                icon_color=DARK_TEXT,
                icon_size=22,
                tooltip="Home",
                style=ft.ButtonStyle(
                    bgcolor=YELLOW,
                    shape=ft.RoundedRectangleBorder(radius=12),
                    padding=12,
                ),
                on_click=lambda e: _on_nav(0),
            ),
            ft.IconButton(
                icon=ft.Icons.EDIT_ROUNDED,
                icon_color=DARK_TEXT,
                icon_size=22,
                tooltip="Editor",
                style=ft.ButtonStyle(
                    bgcolor=ft.Colors.TRANSPARENT,
                    shape=ft.RoundedRectangleBorder(radius=12),
                    padding=12,
                ),
                on_click=lambda e: _on_nav(1),
            ),
            ft.IconButton(
                icon=ft.Icons.DASHBOARD_ROUNDED,
                icon_color=DARK_TEXT,
                icon_size=22,
                tooltip="Dashboard",
                style=ft.ButtonStyle(
                    bgcolor=ft.Colors.TRANSPARENT,
                    shape=ft.RoundedRectangleBorder(radius=12),
                    padding=12,
                ),
                on_click=lambda e: _on_nav(2),
            ),
        ]

        # ── Dev mode badge ─────────────────────────────────────────
        dev_badge = ft.IconButton(
            icon=ft.Icons.DEVELOPER_MODE_ROUNDED,
            icon_color=PURPLE,
            icon_size=22,
            tooltip="開発モード (認証スキップ中)",
            style=ft.ButtonStyle(padding=8),
        )

        activity_bar = ft.Container(
            content=ft.Column(
                [
                    # Logo / brand area
                    ft.Container(
                        content=ft.Text(
                            "LS",
                            size=18,
                            weight=ft.FontWeight.W_900,
                            color=CARD_BG,
                        ),
                        width=40,
                        height=40,
                        bgcolor=BLUE,
                        border_radius=12,
                        alignment=ft.Alignment(0, 0),
                    ),
                    ft.Container(height=16),
                    *nav_buttons,
                    ft.Container(expand=True),
                    dev_badge,
                    ft.IconButton(
                        icon=ft.Icons.SETTINGS_ROUNDED,
                        icon_color=MID_TEXT,
                        icon_size=20,
                        tooltip="Settings",
                        style=ft.ButtonStyle(
                            shape=ft.RoundedRectangleBorder(radius=12),
                            padding=12,
                        ),
                        on_click=lambda e: SettingsDialog(page=page, compiler=compiler).show(),
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=4,
            ),
            width=64,
            bgcolor=SIDEBAR_BG,
            padding=ft.padding.symmetric(vertical=12, horizontal=8),
        )

        # ── Status bar (bottom) ─────────────────────────────────────
        db_label = "Supabase" if db_client.is_supabase else "SQLite"
        scheduler_badge = ft.Container(
            content=ft.Row(
                [
                    ft.Icon(ft.Icons.CIRCLE, size=8, color=GREEN),
                    ft.Text("Scheduler", size=11, color=MID_TEXT),
                ],
                spacing=4,
            ),
            bgcolor=CARD_BG,
            border_radius=10,
            padding=ft.padding.symmetric(horizontal=10, vertical=4),
        )

        status_bar = ft.Container(
            content=ft.Row(
                [
                    scheduler_badge,
                    ft.Container(
                        content=ft.Text(
                            f"DB: {db_label}",
                            size=11,
                            color=MID_TEXT,
                        ),
                        bgcolor=CARD_BG,
                        border_radius=10,
                        padding=ft.padding.symmetric(horizontal=10, vertical=4),
                    ),
                    ft.Container(expand=True),
                    ft.Text("LifeScript v0.1 (dev)", size=11, color=LIGHT_TEXT),
                ],
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            height=32,
            bgcolor=SIDEBAR_BG,
            padding=ft.padding.symmetric(horizontal=16),
        )

        # ── Page layout ─────────────────────────────────────────────
        page.add(
            ft.Column(
                [
                    ft.Row(
                        [activity_bar, content_area],
                        expand=True,
                        spacing=0,
                    ),
                    status_bar,
                ],
                expand=True,
                spacing=0,
            )
        )

        # ── Centralised log polling ─────────────────────────────────
        def _poll() -> None:
            entries = log_queue.drain()
            if entries:
                home_view.receive_logs(entries)
                current = active_view[0]
                if current is not home_view and hasattr(current, "receive_logs"):
                    current.receive_logs(entries)
                running = scheduler.is_running
                scheduler_badge.content.controls[0].color = GREEN if running else CORAL
                page.update()
            t = threading.Timer(1.0, _poll)
            t.daemon = True
            t.start()

        t = threading.Timer(1.0, _poll)
        t.daemon = True
        t.start()

        # ── Window close handler ────────────────────────────────────
        def on_window_event(e: ft.WindowEvent) -> None:
            if e.data == "close":
                scheduler.stop()

        page.window.on_event = on_window_event

    return main
