"""設定画面 — 外部サービス連携・アカウント設定。"""

from __future__ import annotations

import flet as ft

from .. import google_auth
from .app import (
    BG, CARD_BG, CARD_SHADOW, BLUE, GREEN, CORAL, YELLOW, ORANGE,
    DARK_TEXT, MID_TEXT, LIGHT_TEXT, SIDEBAR_BG,
)

_BORDER = "#E8E4DC"


class SettingsView:
    def __init__(self, page: ft.Page) -> None:
        self._page = page

    def build(self) -> ft.Control:
        google_section = self._section_google()
        self._google_section_container = google_section
        return ft.Column([
            self._header(),
            ft.Container(
                content=ft.Column([
                    google_section,
                    ft.Container(height=16),
                    self._section_about(),
                ], spacing=0, scroll=ft.ScrollMode.AUTO),
                expand=True,
                padding=ft.padding.symmetric(horizontal=16),
            ),
        ], expand=True, spacing=0)

    def receive_logs(self, entries: list) -> None:
        pass

    # ------------------------------------------------------------------
    # Header
    # ------------------------------------------------------------------
    def _header(self) -> ft.Container:
        return ft.Container(
            content=ft.Row([
                ft.Icon(ft.Icons.SETTINGS_ROUNDED, size=24, color=DARK_TEXT),
                ft.Text("設定", size=22, weight=ft.FontWeight.W_800, color=DARK_TEXT),
            ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            padding=ft.padding.only(left=16, right=16, top=12, bottom=16),
        )

    # ------------------------------------------------------------------
    # Google連携セクション
    # ------------------------------------------------------------------
    def _section_google(self) -> ft.Container:
        is_configured = google_auth.is_configured()
        is_authed = google_auth.is_authenticated()
        user_email = google_auth.get_user_email()

        # ステータス表示
        if is_authed and user_email:
            status_icon = ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, size=16, color=GREEN)
            status_text = ft.Text(f"連携済み: {user_email}", size=13, color=GREEN,
                                  weight=ft.FontWeight.W_500)
        elif is_configured:
            status_icon = ft.Icon(ft.Icons.CIRCLE_OUTLINED, size=16, color=ORANGE)
            status_text = ft.Text("未認証（認証ボタンを押してください）", size=13, color=ORANGE)
        else:
            status_icon = ft.Icon(ft.Icons.WARNING_ROUNDED, size=16, color=CORAL)
            status_text = ft.Text("未設定（credentials.json が必要です）", size=13, color=CORAL)

        status_row = ft.Row(
            [status_icon, status_text],
            spacing=6, vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        # ボタン群
        buttons: list[ft.Control] = []

        if is_authed:
            buttons.append(ft.ElevatedButton(
                "連携を解除",
                icon=ft.Icons.LINK_OFF_ROUNDED,
                bgcolor=CORAL, color=CARD_BG,
                style=ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius=10),
                    elevation=0,
                ),
                on_click=self._on_revoke_google,
            ))
        elif is_configured:
            buttons.append(ft.ElevatedButton(
                "Googleアカウントを連携",
                icon=ft.Icons.LOGIN_ROUNDED,
                bgcolor=BLUE, color=CARD_BG,
                width=280, height=44,
                style=ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius=10),
                    elevation=0,
                    text_style=ft.TextStyle(size=14, weight=ft.FontWeight.W_600),
                ),
                on_click=self._on_auth_google,
            ))

        # 説明文
        desc_items = [
            ft.Text(
                "Google アカウントを連携すると、以下の機能が使えるようになります:",
                size=13, color=MID_TEXT,
            ),
            ft.Container(height=8),
            self._feature_row(ft.Icons.MAIL_ROUNDED, "Gmail", "未読メールの取得・要約・検索"),
            self._feature_row(ft.Icons.SEND_ROUNDED, "メール送信", "ダリーからメールを送信"),
        ]

        if not is_configured:
            desc_items.extend([
                ft.Container(height=12),
                ft.Container(
                    content=ft.Column([
                        ft.Text("セットアップ手順:", size=13, weight=ft.FontWeight.W_600, color=DARK_TEXT),
                        ft.Container(height=4),
                        ft.Text("1. Google Cloud Console でプロジェクトを作成", size=12, color=MID_TEXT),
                        ft.Text("2. OAuth 2.0 クライアントID（デスクトップアプリ）を作成", size=12, color=MID_TEXT),
                        ft.Text("3. credentials.json をダウンロード", size=12, color=MID_TEXT),
                        ft.Text("4. ~/.lifescript/google_credentials.json に配置", size=12, color=MID_TEXT),
                        ft.Container(height=4),
                        ft.Container(
                            content=ft.Text(
                                "~/.lifescript/google_credentials.json",
                                size=12, color=LIGHT_TEXT, font_family="Courier New",
                                selectable=True,
                            ),
                            bgcolor="#F5F3EE", border_radius=6,
                            padding=ft.padding.symmetric(horizontal=10, vertical=6),
                        ),
                    ]),
                    bgcolor="#FFF9EC",
                    border_radius=14,
                    padding=14,
                    border=ft.border.all(1, "#F0E8D0"),
                ),
            ])

        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Container(
                        content=ft.Icon(ft.Icons.MAIL_ROUNDED, size=20, color=CARD_BG),
                        width=36, height=36, bgcolor="#EA4335", border_radius=12,
                        alignment=ft.Alignment(0, 0),
                    ),
                    ft.Container(width=8),
                    ft.Column([
                        ft.Text("Google 連携", size=16, weight=ft.FontWeight.W_700, color=DARK_TEXT),
                        ft.Text("Gmail の読み取り・送信", size=12, color=MID_TEXT),
                    ], spacing=1),
                ], spacing=6, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Container(height=12),
                status_row,
                ft.Container(height=12),
                *desc_items,
                ft.Container(height=16),
                ft.Row(buttons, spacing=8) if buttons else ft.Container(),
            ], spacing=0),
            bgcolor=CARD_BG,
            border_radius=20,
            padding=20,
            shadow=CARD_SHADOW,
        )

    def _feature_row(self, icon: str, title: str, desc: str) -> ft.Container:
        return ft.Container(
            content=ft.Row([
                ft.Icon(icon, size=16, color=BLUE),
                ft.Text(title, size=13, weight=ft.FontWeight.W_600, color=DARK_TEXT),
                ft.Text(f"— {desc}", size=13, color=MID_TEXT),
            ], spacing=6, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            padding=ft.padding.only(left=8, top=2, bottom=2),
        )

    # ------------------------------------------------------------------
    # About セクション
    # ------------------------------------------------------------------
    def _section_about(self) -> ft.Container:
        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Icon(ft.Icons.INFO_OUTLINE_ROUNDED, size=18, color=BLUE),
                    ft.Text("LifeScript について", size=16, weight=ft.FontWeight.W_700, color=DARK_TEXT),
                ], spacing=8),
                ft.Container(height=8),
                ft.Text("v0.2 — HackU Frontier", size=13, color=MID_TEXT),
                ft.Text("あなたの生活に寄り添うロボット「ダリー」", size=13, color=MID_TEXT),
            ], spacing=0),
            bgcolor=CARD_BG,
            border_radius=20,
            padding=20,
            shadow=CARD_SHADOW,
        )

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def _on_auth_google(self, e: ft.ControlEvent) -> None:
        # ボタンをローディング状態に
        btn = e.control
        btn.text = "ブラウザで認証中..."
        btn.disabled = True
        btn.bgcolor = MID_TEXT
        self._page.update()

        def _on_complete(success: bool, email: str | None) -> None:
            if success:
                btn.text = f"連携完了: {email}"
                btn.bgcolor = GREEN
                btn.icon = ft.Icons.CHECK_ROUNDED
            else:
                btn.text = "認証に失敗しました — もう一度お試しください"
                btn.bgcolor = CORAL
                btn.disabled = False
            # Google連携セクションを最新状態で再描画
            self._rebuild_google_section()
            self._page.update()

        google_auth.authenticate(on_complete=_on_complete)

    def _on_revoke_google(self, e: ft.ControlEvent) -> None:
        google_auth.revoke()
        self._rebuild_google_section()
        self._page.update()

    def _rebuild_google_section(self) -> None:
        """Google連携セクションを最新の認証状態で再構築する。"""
        if hasattr(self, "_google_section_container"):
            new_section = self._section_google()
            self._google_section_container.content = new_section.content
            self._google_section_container.bgcolor = new_section.bgcolor
            self._google_section_container.border = new_section.border
