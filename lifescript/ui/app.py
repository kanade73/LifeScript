"""Flet アプリケーション — LifeScript PC クライアント。

スプラッシュ → ログイン → Home / IDE / Dashboard の3画面構成。
"""

from __future__ import annotations

import threading
import time

import flet as ft

from ..compiler.compiler import Compiler
from ..database.client import db_client
from ..scheduler.scheduler import LifeScriptScheduler
from .. import log_queue

# ── Colour palette ──────────────────────────────────────────────────
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

COLORS = {
    "bg": BG, "sidebar_bg": SIDEBAR_BG, "card_bg": CARD_BG,
    "editor_bg": EDITOR_BG, "editor_fg": EDITOR_FG,
    "yellow": YELLOW, "blue": BLUE, "green": GREEN,
    "coral": CORAL, "purple": PURPLE, "orange": ORANGE,
    "brown": BROWN, "dark_text": DARK_TEXT, "mid_text": MID_TEXT,
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
        page.window.width = 1200
        page.window.height = 800
        page.window.min_width = 900
        page.window.min_height = 600
        page.padding = 0

        # ── ログイン済みユーザー情報 ──────────────────────────
        _user_info: list[dict | None] = [None]

        # ==============================================================
        # Phase 1: スプラッシュ画面
        # ==============================================================
        from .splash_screen import build_splash
        splash = build_splash(page)
        page.add(splash)

        def _after_splash() -> None:
            time.sleep(1.5)
            page.controls.clear()
            _show_login()
            page.update()

        threading.Thread(target=_after_splash, daemon=True).start()

        # ==============================================================
        # Phase 2: ログイン画面
        # ==============================================================
        def _show_login() -> None:
            page.bgcolor = BG
            from .login_screen import build_login
            login_view = build_login(page, on_success=_on_login_success)
            page.controls.clear()
            page.add(login_view)
            page.update()

        def _on_login_success(user: dict) -> None:
            _user_info[0] = user
            page.controls.clear()
            _show_main_app()
            page.update()

        # ==============================================================
        # Phase 3: メインアプリ
        # ==============================================================
        def _show_main_app() -> None:
            page.bgcolor = BG

            from .home_view import HomeView
            from .main_screen import EditorView
            from .dashboard_view import DashboardView
            from .reference_view import ReferenceView
            from .concierge_view import ConciergeView

            # ── DB connect ──────────────────────────────────────
            db_client.connect()
            if db_client.is_connected and not scheduler.is_running:
                scheduler.start()
                scheduler.load_from_db()

            home_view = HomeView(page=page, scheduler=scheduler)
            editor_view = EditorView(page=page, compiler=compiler, scheduler=scheduler)
            dashboard_view = DashboardView(page=page, scheduler=scheduler)
            reference_view = ReferenceView(page=page)
            concierge_view = ConciergeView(page=page, model=compiler.model)

            views = [home_view, editor_view, dashboard_view, reference_view, concierge_view]
            active_view: list = [home_view]

            # ── Content area ─────────────────────────────────────
            content_area = ft.Container(
                content=home_view.build(),
                expand=True,
                bgcolor=BG,
                padding=ft.padding.only(top=8, left=8, right=8, bottom=0),
                border_radius=ft.border_radius.only(top_left=16),
            )

            # ── Sidebar navigation (常時展開) ─────────────────────
            _nav_index = [0]

            nav_items = [
                (ft.Icons.HOME_ROUNDED, "Home"),
                (ft.Icons.CODE_ROUNDED, "IDE"),
                (ft.Icons.DASHBOARD_ROUNDED, "Dashboard"),
                (ft.Icons.MENU_BOOK_ROUNDED, "Reference"),
                (ft.Icons.AUTO_AWESOME_ROUNDED, "Machine"),
            ]

            def _build_nav_row(index: int) -> ft.Container:
                icon, label = nav_items[index]
                is_active = index == _nav_index[0]
                return ft.Container(
                    content=ft.Row([
                        ft.Icon(icon, size=22, color=DARK_TEXT),
                        ft.Text(label, size=13, weight=ft.FontWeight.W_600, color=DARK_TEXT),
                    ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    bgcolor=YELLOW if is_active else ft.Colors.TRANSPARENT,
                    border_radius=12,
                    padding=ft.padding.symmetric(horizontal=12, vertical=10),
                    on_click=lambda e, idx=index: _on_nav(idx),
                    ink=True,
                )

            sidebar_column = ft.Column(spacing=4)

            def _rebuild_sidebar() -> None:
                # ユーザー情報
                user = _user_info[0] or {}
                user_email = user.get("email", "")
                user_display = user_email.split("@")[0] if user_email else "ローカル"

                sidebar_column.controls = [
                    ft.Container(
                        content=ft.Row([
                            ft.Container(
                                content=ft.Text("LS", size=16, weight=ft.FontWeight.W_900, color=CARD_BG),
                                width=36, height=36, bgcolor=BLUE,
                                border_radius=10, alignment=ft.Alignment(0, 0),
                            ),
                            ft.Text("LifeScript", size=14, weight=ft.FontWeight.W_800, color=DARK_TEXT),
                        ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                        padding=ft.padding.only(left=4),
                    ),
                    ft.Container(height=12),
                    *[_build_nav_row(i) for i in range(len(nav_items))],
                    ft.Container(expand=True),
                    # ユーザー情報 + ログアウト
                    ft.Container(
                        content=ft.Row([
                            ft.Container(
                                content=ft.Icon(ft.Icons.PERSON_ROUNDED, size=18, color=CARD_BG),
                                width=32, height=32, bgcolor=MID_TEXT,
                                border_radius=16, alignment=ft.Alignment(0, 0),
                            ),
                            ft.Text(user_display, size=12, color=DARK_TEXT,
                                    weight=ft.FontWeight.W_500, expand=True,
                                    max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                            ft.IconButton(
                                ft.Icons.LOGOUT_ROUNDED, icon_size=16, icon_color=LIGHT_TEXT,
                                tooltip="ログアウト", style=ft.ButtonStyle(padding=4),
                                on_click=lambda e: _on_logout(),
                            ),
                        ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                        padding=ft.padding.only(left=4, top=8),
                        border=ft.border.only(top=ft.BorderSide(1, "#E8E4DC")),
                    ),
                ]

            def _on_nav(index: int) -> None:
                _nav_index[0] = index
                active_view[0] = views[index]
                content_area.content = views[index].build()
                _rebuild_sidebar()
                page.update()

            def _on_logout() -> None:
                _user_info[0] = None
                scheduler.stop()
                page.controls.clear()
                _show_login()
                page.update()

            _rebuild_sidebar()

            activity_bar = ft.Container(
                content=sidebar_column,
                width=200,
                bgcolor=SIDEBAR_BG,
                padding=ft.padding.symmetric(vertical=12, horizontal=8),
            )

            # ── Status bar ───────────────────────────────────────
            db_label = "Supabase" if db_client.is_supabase else "SQLite"
            scheduler_badge = ft.Container(
                content=ft.Row(
                    [ft.Icon(ft.Icons.CIRCLE, size=8, color=GREEN), ft.Text("Scheduler", size=11, color=MID_TEXT)],
                    spacing=4,
                ),
                bgcolor=CARD_BG, border_radius=10,
                padding=ft.padding.symmetric(horizontal=10, vertical=4),
            )

            status_bar = ft.Container(
                content=ft.Row(
                    [
                        scheduler_badge,
                        ft.Container(
                            content=ft.Text(f"DB: {db_label}", size=11, color=MID_TEXT),
                            bgcolor=CARD_BG, border_radius=10,
                            padding=ft.padding.symmetric(horizontal=10, vertical=4),
                        ),
                        ft.Container(
                            content=ft.Text("API: :8000", size=11, color=MID_TEXT),
                            bgcolor=CARD_BG, border_radius=10,
                            padding=ft.padding.symmetric(horizontal=10, vertical=4),
                        ),
                        ft.Container(expand=True),
                        ft.Text("LifeScript v0.2", size=11, color=LIGHT_TEXT),
                    ],
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                height=32, bgcolor=SIDEBAR_BG,
                padding=ft.padding.symmetric(horizontal=16),
            )

            # ── Page layout ──────────────────────────────────────
            page.add(
                ft.Column(
                    [
                        ft.Row([activity_bar, content_area], expand=True, spacing=0),
                        status_bar,
                    ],
                    expand=True, spacing=0,
                )
            )

            # ── Log polling ──────────────────────────────────────
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

        # ── Window close ─────────────────────────────────────
        def on_window_event(e: ft.WindowEvent) -> None:
            if e.data == "close":
                scheduler.stop()

        page.window.on_event = on_window_event

    return main
