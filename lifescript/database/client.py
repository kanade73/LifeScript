"""データベースクライアント — Supabase（本番）+ SQLite（フォールバック）。

SUPABASE_URL と SUPABASE_ANON_KEY が設定されている場合は Supabase に保存し、
iPhone ダッシュボードからリアルタイムで読み取れるようにする。
未設定の場合はローカルの SQLite にフォールバックする（開発用）。
"""

from __future__ import annotations

import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# SQLite fallback paths
# ---------------------------------------------------------------------------
_DB_DIR = Path.home() / ".lifescript"
_DB_PATH = _DB_DIR / "lifescript.db"

_SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS rules (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    title           TEXT    NOT NULL,
    lifescript_code TEXT    NOT NULL,
    compiled_python TEXT    NOT NULL,
    trigger_seconds INTEGER NOT NULL DEFAULT 60,
    status          TEXT    NOT NULL DEFAULT 'active',
    created_at      TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS logs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_id       TEXT,
    message       TEXT    NOT NULL DEFAULT '',
    executed_at   TEXT    NOT NULL,
    result        TEXT    NOT NULL DEFAULT 'success',
    error_message TEXT    NOT NULL DEFAULT ''
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ======================================================================
# Supabase backend
# ======================================================================
class _SupabaseBackend:
    def __init__(self, url: str, key: str) -> None:
        from supabase import create_client

        self._client = create_client(url, key)

    # -- Rules ----------------------------------------------------------
    def save_rule(
        self,
        title: str,
        lifescript_code: str,
        compiled_python: str,
        trigger_seconds: int = 60,
    ) -> dict:
        data = {
            "title": title,
            "lifescript_code": lifescript_code,
            "compiled_python": compiled_python,
            "trigger_seconds": trigger_seconds,
            "status": "active",
            "created_at": _now(),
        }
        resp = self._client.table("rules").insert(data).execute()
        return resp.data[0]

    def get_rules(self) -> list[dict]:
        resp = self._client.table("rules").select("*").eq("status", "active").order("id").execute()
        return resp.data

    def get_rule_by_id(self, rule_id: int) -> dict:
        resp = self._client.table("rules").select("*").eq("id", rule_id).execute()
        if not resp.data:
            raise RuntimeError(f"ルール {rule_id} が見つかりません")
        return resp.data[0]

    def update_rule_python(self, rule_id: str, compiled_python: str) -> None:
        self._client.table("rules").update({"compiled_python": compiled_python}).eq(
            "id", str(rule_id)
        ).execute()

    def update_rule_status(self, rule_id: str, status: str) -> None:
        self._client.table("rules").update({"status": status}).eq("id", str(rule_id)).execute()

    def delete_rule(self, rule_id: str) -> None:
        self.update_rule_status(rule_id, "deleted")

    # -- Logs -----------------------------------------------------------
    def save_log(
        self,
        rule_id: str | None,
        message: str,
        result: str = "success",
        error_message: str = "",
    ) -> None:
        data = {
            "rule_id": str(rule_id) if rule_id else None,
            "message": message,
            "executed_at": _now(),
            "result": result,
            "error_message": error_message,
        }
        self._client.table("logs").insert(data).execute()

    def get_logs(self, rule_id: str | None = None, limit: int = 100) -> list[dict]:
        q = self._client.table("logs").select("*")
        if rule_id:
            q = q.eq("rule_id", str(rule_id))
        resp = q.order("id", desc=True).limit(limit).execute()
        return resp.data


# ======================================================================
# SQLite fallback backend
# ======================================================================
class _SQLiteBackend:
    def __init__(self) -> None:
        self._conn: sqlite3.Connection | None = None
        self._lock = threading.Lock()

    def connect(self) -> None:
        _DB_DIR.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(_SQLITE_SCHEMA)
        self._conn.commit()

    def _execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        with self._lock:
            assert self._conn is not None
            cur = self._conn.execute(sql, params)
            self._conn.commit()
            return cur

    # -- Rules ----------------------------------------------------------
    def save_rule(
        self,
        title: str,
        lifescript_code: str,
        compiled_python: str,
        trigger_seconds: int = 60,
    ) -> dict:
        cur = self._execute(
            """INSERT INTO rules (title, lifescript_code, compiled_python, trigger_seconds, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (title, lifescript_code, compiled_python, trigger_seconds, _now()),
        )
        return self.get_rule_by_id(cur.lastrowid)

    def get_rules(self) -> list[dict]:
        with self._lock:
            assert self._conn is not None
            cur = self._conn.execute("SELECT * FROM rules WHERE status = 'active' ORDER BY id")
            return [dict(row) for row in cur.fetchall()]

    def get_rule_by_id(self, rule_id: int | None) -> dict:
        with self._lock:
            assert self._conn is not None
            cur = self._conn.execute("SELECT * FROM rules WHERE id = ?", (rule_id,))
            row = cur.fetchone()
            if row is None:
                raise RuntimeError(f"ルール {rule_id} が見つかりません")
            return dict(row)

    def update_rule_python(self, rule_id: str, compiled_python: str) -> None:
        self._execute(
            "UPDATE rules SET compiled_python = ? WHERE id = ?",
            (compiled_python, str(rule_id)),
        )

    def update_rule_status(self, rule_id: str, status: str) -> None:
        self._execute("UPDATE rules SET status = ? WHERE id = ?", (status, str(rule_id)))

    def delete_rule(self, rule_id: str) -> None:
        self.update_rule_status(rule_id, "deleted")

    # -- Logs -----------------------------------------------------------
    def save_log(
        self,
        rule_id: str | None,
        message: str,
        result: str = "success",
        error_message: str = "",
    ) -> None:
        self._execute(
            """INSERT INTO logs (rule_id, message, executed_at, result, error_message)
               VALUES (?, ?, ?, ?, ?)""",
            (str(rule_id) if rule_id else None, message, _now(), result, error_message),
        )

    def get_logs(self, rule_id: str | None = None, limit: int = 100) -> list[dict]:
        with self._lock:
            assert self._conn is not None
            if rule_id:
                cur = self._conn.execute(
                    "SELECT * FROM logs WHERE rule_id = ? ORDER BY id DESC LIMIT ?",
                    (str(rule_id), limit),
                )
            else:
                cur = self._conn.execute("SELECT * FROM logs ORDER BY id DESC LIMIT ?", (limit,))
            return [dict(row) for row in cur.fetchall()]


# ======================================================================
# Unified DatabaseClient facade
# ======================================================================
class DatabaseClient:
    """統一 DB インターフェース。Supabase を試行し、失敗時は SQLite にフォールバック。"""

    def __init__(self) -> None:
        self._backend: _SupabaseBackend | _SQLiteBackend | None = None
        self._is_supabase = False

    def connect(self) -> None:
        url = os.getenv("SUPABASE_URL", "")
        key = os.getenv("SUPABASE_ANON_KEY", "")
        if url and key:
            try:
                self._backend = _SupabaseBackend(url, key)
                self._is_supabase = True
                return
            except Exception:
                pass  # Fall through to SQLite
        # SQLite fallback
        sqlite = _SQLiteBackend()
        sqlite.connect()
        self._backend = sqlite
        self._is_supabase = False

    @property
    def is_connected(self) -> bool:
        return self._backend is not None

    @property
    def is_supabase(self) -> bool:
        return self._is_supabase

    # Delegate all methods to the active backend
    def save_rule(self, **kwargs: Any) -> dict:
        assert self._backend is not None
        return self._backend.save_rule(**kwargs)

    def get_rules(self) -> list[dict]:
        assert self._backend is not None
        return self._backend.get_rules()

    def get_rule_by_id(self, rule_id: int | None) -> dict:
        assert self._backend is not None
        return self._backend.get_rule_by_id(rule_id)

    def update_rule_python(self, rule_id: str, compiled_python: str) -> None:
        assert self._backend is not None
        self._backend.update_rule_python(rule_id, compiled_python)

    def update_rule_status(self, rule_id: str, status: str) -> None:
        assert self._backend is not None
        self._backend.update_rule_status(rule_id, status)

    def delete_rule(self, rule_id: str) -> None:
        assert self._backend is not None
        self._backend.delete_rule(rule_id)

    def save_log(
        self,
        rule_id: str | None = None,
        message: str = "",
        result: str = "success",
        error_message: str = "",
    ) -> None:
        assert self._backend is not None
        self._backend.save_log(
            rule_id=rule_id, message=message, result=result, error_message=error_message
        )

    def get_logs(self, rule_id: str | None = None, limit: int = 100) -> list[dict]:
        assert self._backend is not None
        return self._backend.get_logs(rule_id=rule_id, limit=limit)


# Application-wide singleton
db_client = DatabaseClient()
