"""Google OAuth 2.0 認証 — Gmail / Google Calendar 連携用。

~/.lifescript/google_credentials.json にOAuthクライアント情報を配置。
認証後のトークンは ~/.lifescript/google_token.json に保存。
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any

# Google が openid スコープを勝手に追加して返すため、スコープ変更を許容する
os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"

_CREDENTIALS_DIR = Path.home() / ".lifescript"
_CLIENT_SECRETS_FILE = _CREDENTIALS_DIR / "google_credentials.json"
_TOKEN_FILE = _CREDENTIALS_DIR / "google_token.json"

# Gmail readonly + profile
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/userinfo.email",
]


def is_configured() -> bool:
    """Google OAuthのクライアント情報が配置されているか。"""
    return _CLIENT_SECRETS_FILE.exists()


def is_authenticated() -> bool:
    """有効なトークンが存在するか（期限切れはリフレッシュを試みる）。"""
    if not _TOKEN_FILE.exists():
        return False
    try:
        creds = _load_credentials()
        if creds is None:
            return False
        if creds.valid:
            return True
        # 期限切れだがrefresh_tokenがあればリフレッシュ
        if creds.expired and creds.refresh_token:
            import google.auth.transport.requests
            request = google.auth.transport.requests.Request()
            creds.refresh(request)
            email = get_user_email()
            _save_credentials(creds, email)
            return creds.valid
        return False
    except Exception:
        return False


def get_user_email() -> str | None:
    """認証済みユーザーのメールアドレスを返す。"""
    if not _TOKEN_FILE.exists():
        return None
    try:
        data = json.loads(_TOKEN_FILE.read_text(encoding="utf-8"))
        return data.get("_email")
    except Exception:
        return None


def authenticate(on_complete: callable | None = None) -> None:
    """OAuth認証フローを開始する（ブラウザが開く）。

    完了時に on_complete(success: bool, email: str | None) が呼ばれる。
    """
    def _run() -> None:
        try:
            from google_auth_oauthlib.flow import InstalledAppFlow

            if not _CLIENT_SECRETS_FILE.exists():
                if on_complete:
                    on_complete(False, None)
                return

            flow = InstalledAppFlow.from_client_secrets_file(
                str(_CLIENT_SECRETS_FILE), SCOPES
            )
            # success_message でブラウザに「閉じてOK」と表示
            creds = flow.run_local_server(
                port=8090,
                open_browser=True,
                success_message="認証が完了しました！このタブを閉じてアプリに戻ってください。",
            )

            if creds is None:
                print("Google OAuth: credentials is None after flow")
                if on_complete:
                    on_complete(False, None)
                return

            # メールアドレスを取得
            email = _fetch_email(creds)

            # トークン保存
            _save_credentials(creds, email)

            print(f"Google OAuth success: {email}, token saved to {_TOKEN_FILE}")
            if on_complete:
                on_complete(True, email)
        except Exception as e:
            import traceback
            print(f"Google OAuth error: {e}")
            traceback.print_exc()
            if on_complete:
                on_complete(False, None)

    threading.Thread(target=_run, daemon=True).start()


def revoke() -> None:
    """認証を取り消し、トークンを削除する。"""
    try:
        creds = _load_credentials()
        if creds:
            import google.auth.transport.requests
            request = google.auth.transport.requests.Request()
            try:
                from google.oauth2.credentials import Credentials
                if hasattr(creds, 'revoke'):
                    creds.revoke(request)
            except Exception:
                pass
    except Exception:
        pass
    _TOKEN_FILE.unlink(missing_ok=True)


def get_credentials():
    """有効な認証情報を返す。必要ならリフレッシュ。"""
    creds = _load_credentials()
    if creds is None:
        return None

    if creds.expired and creds.refresh_token:
        try:
            import google.auth.transport.requests
            request = google.auth.transport.requests.Request()
            creds.refresh(request)
            email = get_user_email()
            _save_credentials(creds, email)
        except Exception:
            return None

    return creds


def _load_credentials():
    """トークンファイルから認証情報を読み込む。"""
    if not _TOKEN_FILE.exists():
        return None
    try:
        from google.oauth2.credentials import Credentials
        data = json.loads(_TOKEN_FILE.read_text(encoding="utf-8"))
        # _email はメタデータなので除外
        token_data = {k: v for k, v in data.items() if not k.startswith("_")}
        creds = Credentials.from_authorized_user_info(token_data, SCOPES)
        return creds
    except Exception:
        return None


def _save_credentials(creds, email: str | None = None) -> None:
    """認証情報をファイルに保存する。"""
    _CREDENTIALS_DIR.mkdir(parents=True, exist_ok=True)
    data = json.loads(creds.to_json())
    if email:
        data["_email"] = email
    _TOKEN_FILE.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def _fetch_email(creds) -> str | None:
    """認証情報からGmailアドレスを取得する。"""
    try:
        from googleapiclient.discovery import build
        service = build("oauth2", "v2", credentials=creds)
        info = service.userinfo().get().execute()
        return info.get("email")
    except Exception:
        return None
