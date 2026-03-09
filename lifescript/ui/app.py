"""Flet application entry point - Miro-inspired pop design with VSCode-like structure."""

from __future__ import annotations

import threading

import flet as ft

from ..compiler.compiler import Compiler
from ..scheduler.scheduler import LifeScriptScheduler
from .. import log_queue

# ── Miro-inspired colour palette ────────────────────────────────────
BG = "#FAFAF8"
SIDEBAR_BG = "#F0EDE6"
CARD_BG = "#FFFFFF"
EDITOR_BG = "#2D2B27"
EDITOR_FG = "#E8E4DC"
YELLOW = "#FFD02F"
BLUE = "#4262FF"
GREEN = "#00C875"
CORAL = "#FF7575"
PURPLE = "#9B59B6"
DARK_TEXT = "#2D2B27"
MID_TEXT = "#6B6560"
LIGHT_TEXT = "#A09A93"

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
    "dark_text": DARK_TEXT,
    "mid_text": MID_TEXT,
    "light_text": LIGHT_TEXT,
}


def create_app(compiler: Compiler, scheduler: LifeScriptScheduler):
    """Return a Flet main function bound to the given compiler and scheduler."""

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

        from .main_screen import EditorView  # noqa: PLC0415
        from .dashboard_view import DashboardView  # noqa: PLC0415
        from .settings_screen import SettingsDialog  # noqa: PLC0415

        editor_view = EditorView(page=page, compiler=compiler, scheduler=scheduler)
        dashboard_view = DashboardView(page=page, scheduler=scheduler)

        active_view: list = [editor_view]

        # ── Content area ────────────────────────────────────────────
        content_area = ft.Container(
            content=editor_view.build(),
            expand=True,
            bgcolor=BG,
            padding=ft.padding.only(top=8, left=8, right=8, bottom=0),
            border_radius=ft.border_radius.only(top_left=16),
        )

        # ── Activity bar (left icon strip — Miro style) ────────────
        def _on_nav(index: int) -> None:
            if index == 0:
                active_view[0] = editor_view
                content_area.content = editor_view.build()
            else:
                active_view[0] = dashboard_view
                content_area.content = dashboard_view.build()
            # Update active indicator styling
            for i, btn in enumerate(nav_buttons):
                btn.style = ft.ButtonStyle(
                    bgcolor=YELLOW if i == index else ft.Colors.TRANSPARENT,
                    shape=ft.RoundedRectangleBorder(radius=12),
                    padding=12,
                )
            page.update()

        nav_buttons = [
            ft.IconButton(
                icon=ft.Icons.EDIT_ROUNDED,
                icon_color=DARK_TEXT,
                icon_size=22,
                tooltip="Editor",
                style=ft.ButtonStyle(
                    bgcolor=YELLOW,
                    shape=ft.RoundedRectangleBorder(radius=12),
                    padding=12,
                ),
                on_click=lambda e: _on_nav(0),
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
                on_click=lambda e: _on_nav(1),
            ),
        ]

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
                    ft.Container(expand=True),
                    ft.Text("LifeScript v0.1", size=11, color=LIGHT_TEXT),
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
                active_view[0].receive_logs(entries)
                # Update status bar scheduler indicator
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
