"""スプラッシュ画面 — アプリ起動時のブランディング表示。"""

from __future__ import annotations

import flet as ft

from .app import BG, BLUE, CARD_BG, DARK_TEXT, LIGHT_TEXT, MID_TEXT, YELLOW


def build_splash(page: ft.Page) -> ft.Container:
    """スプラッシュ画面を構築する。"""
    return ft.Container(
        content=ft.Column([
            ft.Container(expand=True),
            # Logo
            ft.Container(
                content=ft.Text("LS", size=48, weight=ft.FontWeight.W_900, color=CARD_BG),
                width=100, height=100, bgcolor=BLUE,
                border_radius=24, alignment=ft.Alignment(0, 0),
                shadow=ft.BoxShadow(
                    spread_radius=0, blur_radius=30,
                    color=f"{BLUE}44", offset=ft.Offset(0, 8),
                ),
            ),
            ft.Container(height=24),
            ft.Text("LifeScript", size=36, weight=ft.FontWeight.W_800, color=DARK_TEXT),
            ft.Container(height=8),
            ft.Text(
                "あなたの生活文脈を読み取るマシン",
                size=16, color=MID_TEXT,
            ),
            ft.Container(height=48),
            ft.ProgressRing(
                width=28, height=28,
                stroke_width=3, color=YELLOW,
            ),
            ft.Container(height=12),
            ft.Text("起動中...", size=14, color=LIGHT_TEXT),
            ft.Container(expand=True),
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER,
           alignment=ft.MainAxisAlignment.CENTER),
        expand=True,
        bgcolor=BG,
        alignment=ft.Alignment(0, 0),
    )
