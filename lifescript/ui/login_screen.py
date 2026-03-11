"""Login screen - Miro-style pop design with email + password authentication."""

from __future__ import annotations

import threading

import flet as ft

from ..auth.auth import auth_client


# ── Miro-inspired colour palette (shared with app.py) ───────────────
BG = "#FAFAF8"
CARD_BG = "#FFFFFF"
YELLOW = "#FFD02F"
BLUE = "#4262FF"
GREEN = "#00C875"
CORAL = "#FF7575"
PURPLE = "#9B59B6"
DARK_TEXT = "#2D2B27"
MID_TEXT = "#6B6560"
LIGHT_TEXT = "#A09A93"


class LoginScreen:
    """Full-screen login / sign-up view."""

    def __init__(self, page: ft.Page, on_login_success) -> None:
        self._page = page
        self._on_login_success = on_login_success

        self._email = ft.TextField(
            label="メールアドレス",
            hint_text="you@example.com",
            keyboard_type=ft.KeyboardType.EMAIL,
            border_radius=12,
            border_color="#E8E4DC",
            focused_border_color=BLUE,
            width=340,
            on_submit=lambda e: self._password.focus(),
        )
        self._password = ft.TextField(
            label="パスワード",
            hint_text="••••••••",
            password=True,
            can_reveal_password=True,
            border_radius=12,
            border_color="#E8E4DC",
            focused_border_color=BLUE,
            width=340,
            on_submit=lambda e: self._do_sign_in_click(e),
        )
        self._status = ft.Text("", size=13, color=CORAL, text_align=ft.TextAlign.CENTER)
        self._loading = ft.ProgressRing(width=20, height=20, visible=False, color=BLUE)

    def build(self) -> ft.Control:
        """Return the login screen as a Flet Control."""
        return ft.Container(
            content=ft.Column(
                [
                    # ── Logo ──────────────────────────────────────
                    ft.Container(
                        content=ft.Text(
                            "LS",
                            size=32,
                            weight=ft.FontWeight.W_900,
                            color=CARD_BG,
                        ),
                        width=64,
                        height=64,
                        bgcolor=BLUE,
                        border_radius=18,
                        alignment=ft.Alignment(0, 0),
                    ),
                    ft.Text(
                        "LifeScript",
                        size=28,
                        weight=ft.FontWeight.W_800,
                        color=DARK_TEXT,
                    ),
                    ft.Text(
                        "暮らしにコードを書け",
                        size=14,
                        color=MID_TEXT,
                    ),
                    ft.Container(height=16),
                    # ── Card ──────────────────────────────────────
                    ft.Container(
                        content=ft.Column(
                            [
                                self._email,
                                self._password,
                                ft.Container(height=4),
                                self._status,
                                ft.Row(
                                    [self._loading],
                                    alignment=ft.MainAxisAlignment.CENTER,
                                ),
                                ft.ElevatedButton(
                                    "ログイン",
                                    icon=ft.Icons.LOGIN_ROUNDED,
                                    bgcolor=BLUE,
                                    color=CARD_BG,
                                    width=340,
                                    height=44,
                                    style=ft.ButtonStyle(
                                        shape=ft.RoundedRectangleBorder(radius=12),
                                        elevation=0,
                                    ),
                                    on_click=self._do_sign_in_click,
                                ),
                                ft.TextButton(
                                    "アカウントを作成",
                                    style=ft.ButtonStyle(color=BLUE),
                                    on_click=self._do_sign_up_click,
                                ),
                            ],
                            spacing=12,
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        bgcolor=CARD_BG,
                        border_radius=20,
                        padding=32,
                        width=400,
                        shadow=ft.BoxShadow(
                            spread_radius=0,
                            blur_radius=20,
                            color="#1a000000",
                            offset=ft.Offset(0, 4),
                        ),
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=8,
            ),
            expand=True,
            bgcolor=BG,
            alignment=ft.Alignment(0, 0),
        )

    # ── Actions ───────────────────────────────────────────────────────

    def _set_loading(self, loading: bool) -> None:
        self._loading.visible = loading
        self._page.update()

    def _set_status(self, msg: str, color: str = CORAL) -> None:
        self._status.value = msg
        self._status.color = color
        self._page.update()

    def _do_sign_in_click(self, e) -> None:
        email = self._email.value.strip()
        password = self._password.value.strip()
        if not email or not password:
            self._set_status("メールアドレスとパスワードを入力してください。")
            return
        self._set_loading(True)
        self._set_status("")
        threading.Thread(
            target=self._sign_in_bg, args=(email, password), daemon=True
        ).start()

    def _sign_in_bg(self, email: str, password: str) -> None:
        try:
            auth_client.sign_in(email, password)
            self._set_loading(False)
            self._set_status("ログイン成功！", GREEN)
            self._on_login_success()
        except Exception as ex:
            self._set_loading(False)
            self._set_status(str(ex))

    def _do_sign_up_click(self, e) -> None:
        email = self._email.value.strip()
        password = self._password.value.strip()
        if not email or not password:
            self._set_status("メールアドレスとパスワードを入力してください。")
            return
        if len(password) < 6:
            self._set_status("パスワードは6文字以上にしてください。")
            return
        self._set_loading(True)
        self._set_status("")
        threading.Thread(
            target=self._sign_up_bg, args=(email, password), daemon=True
        ).start()

    def _sign_up_bg(self, email: str, password: str) -> None:
        try:
            auth_client.sign_up(email, password)
            self._set_loading(False)
            self._set_status("アカウント作成成功！", GREEN)
            self._on_login_success()
        except Exception as ex:
            self._set_loading(False)
            self._set_status(str(ex))
