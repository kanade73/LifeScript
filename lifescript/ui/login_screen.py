"""ログイン / サインアップ画面 — Supabase Auth 連携。"""

from __future__ import annotations

from typing import Callable

import flet as ft

from .app import (
    BG, BLUE, CARD_BG, CORAL, DARK_TEXT,
    GREEN, LIGHT_TEXT, MID_TEXT, YELLOW,
)


def build_login(page: ft.Page, on_success: Callable[[dict], None]) -> ft.Container:
    """ログイン画面を構築する。on_success にユーザー情報 dict を渡す。"""

    _mode = ["login"]  # "login" or "signup"

    error_text = ft.Text("", size=13, color=CORAL, visible=False)
    success_text = ft.Text("", size=13, color=GREEN, visible=False)

    email_field = ft.TextField(
        label="メールアドレス",
        prefix_icon=ft.Icons.EMAIL_ROUNDED,
        text_size=15,
        border_radius=12,
        bgcolor=CARD_BG,
        border_color="#E8E4DC",
        focused_border_color=BLUE,
        content_padding=ft.padding.symmetric(horizontal=16, vertical=14),
        width=360,
    )
    password_field = ft.TextField(
        label="パスワード",
        prefix_icon=ft.Icons.LOCK_ROUNDED,
        password=True,
        can_reveal_password=True,
        text_size=15,
        border_radius=12,
        bgcolor=CARD_BG,
        border_color="#E8E4DC",
        focused_border_color=BLUE,
        content_padding=ft.padding.symmetric(horizontal=16, vertical=14),
        width=360,
    )

    action_button = ft.ElevatedButton(
        "ログイン",
        icon=ft.Icons.LOGIN_ROUNDED,
        bgcolor=BLUE,
        color=CARD_BG,
        width=360,
        height=48,
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=12),
            elevation=0,
            text_style=ft.TextStyle(size=15, weight=ft.FontWeight.W_600),
        ),
    )

    toggle_text = ft.Text("", size=14, color=MID_TEXT)
    toggle_link = ft.TextButton(
        "アカウントを作成",
        style=ft.ButtonStyle(color=BLUE, padding=0),
    )

    skip_button = ft.TextButton(
        "ログインせずに使う",
        icon=ft.Icons.ARROW_FORWARD_ROUNDED,
        style=ft.ButtonStyle(color=LIGHT_TEXT, padding=ft.padding.symmetric(horizontal=8)),
    )

    def _set_error(msg: str) -> None:
        error_text.value = msg
        error_text.visible = bool(msg)
        success_text.visible = False
        page.update()

    def _set_success(msg: str) -> None:
        success_text.value = msg
        success_text.visible = bool(msg)
        error_text.visible = False
        page.update()

    def _update_mode() -> None:
        is_login = _mode[0] == "login"
        action_button.text = "ログイン" if is_login else "アカウント作成"
        action_button.icon = ft.Icons.LOGIN_ROUNDED if is_login else ft.Icons.PERSON_ADD_ROUNDED
        toggle_text.value = "アカウントをお持ちでない方" if is_login else "アカウントをお持ちの方"
        toggle_link.text = "アカウントを作成" if is_login else "ログイン"
        error_text.visible = False
        success_text.visible = False
        page.update()

    def _toggle_mode(e: ft.ControlEvent) -> None:
        _mode[0] = "signup" if _mode[0] == "login" else "login"
        _update_mode()

    def _on_submit(e: ft.ControlEvent) -> None:
        email = (email_field.value or "").strip()
        password = (password_field.value or "").strip()

        if not email:
            _set_error("メールアドレスを入力してください")
            return
        if not password:
            _set_error("パスワードを入力してください")
            return
        if len(password) < 6:
            _set_error("パスワードは6文字以上にしてください")
            return

        import os
        url = os.getenv("SUPABASE_URL", "")
        key = os.getenv("SUPABASE_ANON_KEY", "")
        if not url or not key:
            _set_error("Supabase の設定がありません (.env を確認)")
            return

        try:
            from supabase import create_client
            client = create_client(url, key)

            if _mode[0] == "signup":
                resp = client.auth.sign_up({
                    "email": email,
                    "password": password,
                })
                if resp.user:
                    _set_success("アカウントを作成しました")
                    on_success({
                        "id": resp.user.id,
                        "email": resp.user.email,
                    })
                else:
                    _set_error("アカウント作成に失敗しました")
            else:
                resp = client.auth.sign_in_with_password({
                    "email": email,
                    "password": password,
                })
                if resp.user:
                    on_success({
                        "id": resp.user.id,
                        "email": resp.user.email,
                    })
                else:
                    _set_error("ログインに失敗しました")
        except Exception as ex:
            msg = str(ex)
            if "Invalid login" in msg or "invalid" in msg.lower():
                _set_error("メールアドレスまたはパスワードが正しくありません")
            elif "already" in msg.lower() or "registered" in msg.lower():
                _set_error("このメールアドレスは既に登録されています")
            else:
                _set_error(f"エラー: {msg[:100]}")

    def _on_skip(e: ft.ControlEvent) -> None:
        on_success({"id": "local", "email": ""})

    action_button.on_click = _on_submit
    toggle_link.on_click = _toggle_mode
    skip_button.on_click = _on_skip

    password_field.on_submit = _on_submit
    email_field.on_submit = lambda e: password_field.focus()

    _update_mode()

    return ft.Container(
        content=ft.Column([
            ft.Container(expand=True),
            # ロゴ
            ft.Container(
                content=ft.Text("LS", size=40, weight=ft.FontWeight.W_900, color=CARD_BG),
                width=80, height=80, bgcolor=BLUE,
                border_radius=20, alignment=ft.Alignment(0, 0),
                shadow=ft.BoxShadow(
                    spread_radius=0, blur_radius=24,
                    color=f"{BLUE}33", offset=ft.Offset(0, 6),
                ),
            ),
            ft.Container(height=16),
            ft.Text("LifeScript", size=28, weight=ft.FontWeight.W_800, color=DARK_TEXT),
            ft.Container(height=4),
            ft.Text(
                "あなたの生活文脈を読み取り、能動的に動くマシン",
                size=14, color=MID_TEXT,
            ),
            ft.Container(height=36),
            # フォーム
            email_field,
            ft.Container(height=12),
            password_field,
            ft.Container(height=8),
            ft.Container(content=error_text, width=360),
            ft.Container(content=success_text, width=360),
            ft.Container(height=16),
            action_button,
            ft.Container(height=14),
            ft.Row([
                toggle_text,
                toggle_link,
            ], spacing=4, alignment=ft.MainAxisAlignment.CENTER),
            ft.Container(height=20),
            ft.Divider(height=1, color="#E8E4DC", thickness=1),
            ft.Container(height=12),
            skip_button,
            ft.Container(expand=True),
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
        expand=True,
        bgcolor=BG,
    )
