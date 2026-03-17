"""認証管理 — Supabase Auth + セッション永続化。"""

from __future__ import annotations

import json
import os
from pathlib import Path

from dotenv import load_dotenv

# .env を確実に読む
load_dotenv(Path(__file__).resolve().parent.parent / ".env")
load_dotenv(Path.home() / ".lifescript" / ".env")

_SESSION_DIR = Path.home() / ".lifescript"
_SESSION_FILE = _SESSION_DIR / "session.json"


def save_session(data: dict) -> None:
    """セッション情報をローカルに保存。"""
    _SESSION_DIR.mkdir(parents=True, exist_ok=True)
    _SESSION_FILE.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def load_session() -> dict | None:
    """保存済みセッションを読み込み。なければ None。"""
    if not _SESSION_FILE.exists():
        return None
    try:
        data = json.loads(_SESSION_FILE.read_text(encoding="utf-8"))
        return data if data.get("email") else None
    except Exception:
        return None


def clear_session() -> None:
    """セッション情報を削除。"""
    _SESSION_FILE.unlink(missing_ok=True)


def try_restore_session() -> dict | None:
    """保存済みセッションでSupabaseに再ログインを試みる。
    成功すればユーザー情報を返す。失敗すれば None。"""
    session = load_session()
    if not session:
        return None

    refresh_token = session.get("refresh_token")
    if not refresh_token:
        # refresh_tokenがない場合はemail/passwordで再認証は不可
        # ただしユーザー情報は残っているのでローカルモードとして返す
        return session

    url = os.getenv("SUPABASE_URL", "")
    key = os.getenv("SUPABASE_ANON_KEY", "")
    if not url or not key:
        return session  # Supabase未設定ならローカル情報で続行

    try:
        from supabase import create_client
        client = create_client(url, key)
        resp = client.auth.refresh_session(refresh_token)
        if resp.user:
            # 新しいトークンで更新保存
            new_session = {
                "id": resp.user.id,
                "email": resp.user.email,
                "refresh_token": resp.session.refresh_token if resp.session else refresh_token,
            }
            save_session(new_session)
            return new_session
    except Exception:
        pass

    # refresh失敗でもローカル情報は返す（オフライン対応）
    return session


def sign_in(email: str, password: str) -> dict:
    """メール/パスワードでログイン。成功時にセッションを保存して返す。
    失敗時は例外を送出。"""
    url = os.getenv("SUPABASE_URL", "")
    key = os.getenv("SUPABASE_ANON_KEY", "")
    if not url or not key:
        raise RuntimeError("Supabase の設定がありません (.env を確認)")

    from supabase import create_client
    client = create_client(url, key)

    resp = client.auth.sign_in_with_password({
        "email": email,
        "password": password,
    })

    if not resp.user:
        raise RuntimeError("ログインに失敗しました")

    session_data = {
        "id": resp.user.id,
        "email": resp.user.email,
        "refresh_token": resp.session.refresh_token if resp.session else "",
    }
    save_session(session_data)
    return session_data


def sign_up(email: str, password: str) -> dict:
    """アカウント作成。成功時にセッションを保存して返す。"""
    url = os.getenv("SUPABASE_URL", "")
    key = os.getenv("SUPABASE_ANON_KEY", "")
    if not url or not key:
        raise RuntimeError("Supabase の設定がありません (.env を確認)")

    from supabase import create_client
    client = create_client(url, key)

    resp = client.auth.sign_up({
        "email": email,
        "password": password,
    })

    if not resp.user:
        raise RuntimeError("アカウント作成に失敗しました")

    session_data = {
        "id": resp.user.id,
        "email": resp.user.email,
        "refresh_token": resp.session.refresh_token if resp.session else "",
    }
    save_session(session_data)
    return session_data
