"""Supabase 認証クライアント — メール + パスワード認証。

環境変数の SUPABASE_URL と SUPABASE_ANON_KEY を使用。
ユーザーはメールアドレスとパスワードだけでログインできる。
（現在は開発モードでバイパス中）
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any


@dataclass
class AuthSession:
    """Supabase 認証セッションの軽量表現。"""

    access_token: str
    refresh_token: str
    user_id: str
    email: str


class AuthClient:
    """Supabase Auth をラップしたメール + パスワード認証クライアント。"""

    def __init__(self) -> None:
        self._client: Any = None
        self._session: AuthSession | None = None

    def _ensure_client(self) -> None:
        """環境変数から Supabase クライアントを遅延初期化する。"""
        if self._client is not None:
            return
        url = os.getenv("SUPABASE_URL", "")
        key = os.getenv("SUPABASE_ANON_KEY", "")
        if not url or not key:
            raise RuntimeError("SUPABASE_URL と SUPABASE_ANON_KEY を .env に設定してください。")
        from supabase import create_client

        self._client = create_client(url, key)

    @property
    def is_authenticated(self) -> bool:
        return self._session is not None

    @property
    def session(self) -> AuthSession | None:
        return self._session

    def sign_up(self, email: str, password: str) -> AuthSession:
        """新規ユーザーを登録し、セッションを返す。"""
        self._ensure_client()
        resp = self._client.auth.sign_up({"email": email, "password": password})
        if resp.user is None:
            raise RuntimeError("新規登録に失敗しました。メールアドレスを確認してください。")
        if resp.session is None:
            # Email confirmation required
            raise RuntimeError(
                "確認メールを送信しました。メール内のリンクをクリックしてから再度ログインしてください。"
            )
        self._session = AuthSession(
            access_token=resp.session.access_token,
            refresh_token=resp.session.refresh_token,
            user_id=resp.user.id,
            email=email,
        )
        return self._session

    def sign_in(self, email: str, password: str) -> AuthSession:
        """メール + パスワードでログインし、セッションを返す。"""
        self._ensure_client()
        resp = self._client.auth.sign_in_with_password({"email": email, "password": password})
        if resp.user is None or resp.session is None:
            raise RuntimeError(
                "ログインに失敗しました。メールアドレスとパスワードを確認してください。"
            )
        self._session = AuthSession(
            access_token=resp.session.access_token,
            refresh_token=resp.session.refresh_token,
            user_id=resp.user.id,
            email=email,
        )
        return self._session

    def sign_out(self) -> None:
        """ログアウトしてセッションを破棄する。"""
        if self._client is not None:
            try:
                self._client.auth.sign_out()
            except Exception:
                pass  # Best-effort
        self._session = None

    def restore_session(self) -> bool:
        """既存セッションの復元を試みる。成功時に True を返す。"""
        self._ensure_client()
        try:
            resp = self._client.auth.get_session()
            if resp is not None and hasattr(resp, "access_token"):
                user = self._client.auth.get_user(resp.access_token)
                if user and user.user:
                    self._session = AuthSession(
                        access_token=resp.access_token,
                        refresh_token=resp.refresh_token,
                        user_id=user.user.id,
                        email=user.user.email or "",
                    )
                    return True
        except Exception:
            pass
        return False


# Application-wide singleton
auth_client = AuthClient()
