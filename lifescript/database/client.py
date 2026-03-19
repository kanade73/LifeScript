"""データベースクライアント — Supabase（本番）+ SQLite（フォールバック）。

新仕様のテーブル: scripts, calendar_events, machine_logs, streaks
"""

from __future__ import annotations

import os
import json
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

_DB_DIR = Path.home() / ".lifescript"
_DB_PATH = _DB_DIR / "lifescript.db"

_SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS scripts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         TEXT DEFAULT 'local',
    name            TEXT DEFAULT '',
    dsl_text        TEXT NOT NULL,
    compiled_python TEXT DEFAULT '',
    trigger_json    TEXT DEFAULT '',
    active          INTEGER DEFAULT 1,
    created_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS calendar_events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         TEXT DEFAULT 'local',
    title           TEXT NOT NULL,
    start_at        TEXT NOT NULL,
    end_at          TEXT,
    note            TEXT DEFAULT '',
    source          TEXT NOT NULL DEFAULT 'user',
    created_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS machine_logs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         TEXT DEFAULT 'local',
    action_type     TEXT NOT NULL,
    content         TEXT NOT NULL DEFAULT '',
    triggered_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS streaks (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         TEXT DEFAULT 'local',
    habit_name      TEXT NOT NULL,
    count           INTEGER DEFAULT 0,
    last_date       TEXT
);
"""


_JST = timezone(timedelta(hours=9))


def _now() -> str:
    return datetime.now(_JST).isoformat()


def _today() -> str:
    return datetime.now(_JST).strftime("%Y-%m-%d")


# ======================================================================
# Supabase backend
# ======================================================================
class _SupabaseBackend:
    def __init__(self, url: str, key: str) -> None:
        from supabase import create_client

        self._client = create_client(url, key)

    @staticmethod
    def _is_real_uid(user_id: str) -> bool:
        """user_idがSupabase Auth由来の本物のUUIDかどうか判定。"""
        return bool(user_id) and user_id != "local"

    def _filter_uid(self, query: Any, user_id: str) -> Any:
        """user_idでフィルタ。localならNULL、それ以外はeq。"""
        if self._is_real_uid(user_id):
            return query.eq("user_id", user_id)
        return query.is_("user_id", "null")

    def _insert_uid(self, data: dict, user_id: str) -> dict:
        """INSERT用dictにuser_idを追加。localならキーを含めない(NULL)。"""
        if self._is_real_uid(user_id):
            data["user_id"] = user_id
        return data

    # -- Scripts --------------------------------------------------------
    def save_script(
        self,
        dsl_text: str,
        compiled_python: str,
        user_id: str = "local",
        name: str = "",
        trigger: dict | None = None,
    ) -> dict:
        data: dict[str, Any] = {
            "dsl_text": dsl_text,
            "compiled_python": compiled_python,
            "active": True,
        }
        if trigger is not None:
            data["trigger_json"] = json.dumps(trigger, ensure_ascii=False)
        self._insert_uid(data, user_id)
        if name:
            data["name"] = name
        try:
            resp = self._client.table("scripts").insert(data).execute()
            return resp.data[0]
        except Exception:
            # 追加カラムが未反映な環境向けのフォールバック
            data.pop("name", None)
            data.pop("trigger_json", None)
            resp = self._client.table("scripts").insert(data).execute()
            return resp.data[0]

    def get_scripts(self, user_id: str = "local") -> list[dict]:
        q = self._client.table("scripts").select("*").eq("active", True)
        q = self._filter_uid(q, user_id)
        resp = q.order("id").execute()
        return resp.data

    def get_script_by_id(self, script_id: int) -> dict:
        resp = self._client.table("scripts").select("*").eq("id", script_id).execute()
        if not resp.data:
            raise RuntimeError(f"スクリプト {script_id} が見つかりません")
        return resp.data[0]

    def update_script(self, script_id: int, **kwargs: Any) -> None:
        try:
            self._client.table("scripts").update(kwargs).eq("id", script_id).execute()
        except Exception:
            # 追加カラム未反映な環境向けのフォールバック
            kwargs.pop("name", None)
            kwargs.pop("trigger_json", None)
            if kwargs:
                self._client.table("scripts").update(kwargs).eq("id", script_id).execute()

    def delete_script(self, script_id: int) -> None:
        self._client.table("scripts").update({"active": False}).eq("id", script_id).execute()

    # -- Calendar Events ------------------------------------------------
    def add_event(
        self,
        title: str,
        start_at: str,
        end_at: str | None = None,
        note: str = "",
        source: str = "user",
        user_id: str = "local",
    ) -> dict:
        data = {
            "title": title,
            "start_at": start_at,
            "end_at": end_at,
            "note": note,
            "source": source,
        }
        self._insert_uid(data, user_id)
        resp = self._client.table("calendar_events").insert(data).execute()
        return resp.data[0]

    def get_events(
        self,
        user_id: str = "local",
        keyword: str | None = None,
        start_from: str | None = None,
        start_to: str | None = None,
    ) -> list[dict]:
        q = self._client.table("calendar_events").select("*")
        q = self._filter_uid(q, user_id)
        if keyword:
            q = q.ilike("title", f"%{keyword}%")
        if start_from:
            q = q.gte("start_at", start_from)
        if start_to:
            q = q.lte("start_at", start_to)
        resp = q.order("start_at").execute()
        return resp.data

    def delete_event(self, event_id: int) -> None:
        self._client.table("calendar_events").delete().eq("id", event_id).execute()

    def update_event(self, event_id: int, **kwargs: Any) -> None:
        self._client.table("calendar_events").update(kwargs).eq("id", event_id).execute()

    # -- Machine Logs ---------------------------------------------------
    def add_machine_log(
        self,
        action_type: str,
        content: str,
        user_id: str = "local",
    ) -> dict:
        data = {
            "action_type": action_type,
            "content": content,
        }
        self._insert_uid(data, user_id)
        resp = self._client.table("machine_logs").insert(data).execute()
        return resp.data[0]

    def get_machine_logs(self, user_id: str = "local", limit: int = 50) -> list[dict]:
        q = self._client.table("machine_logs").select("*")
        q = self._filter_uid(q, user_id)
        resp = q.order("id", desc=True).limit(limit).execute()
        return resp.data

    def delete_machine_log(self, log_id: int) -> None:
        self._client.table("machine_logs").delete().eq("id", log_id).execute()

    # -- Streaks --------------------------------------------------------
    def get_streak(self, habit_name: str, user_id: str = "local") -> int:
        q = self._client.table("streaks").select("count")
        q = self._filter_uid(q, user_id)
        resp = q.eq("habit_name", habit_name).execute()
        if resp.data:
            return resp.data[0]["count"]
        return 0

    def update_streak(self, habit_name: str, count: int, user_id: str = "local") -> None:
        q = self._client.table("streaks").select("id")
        q = self._filter_uid(q, user_id)
        resp = q.eq("habit_name", habit_name).execute()
        if resp.data:
            self._client.table("streaks").update(
                {"count": count, "last_date": _today()}
            ).eq("id", resp.data[0]["id"]).execute()
        else:
            data = {
                "habit_name": habit_name,
                "count": count,
                "last_date": _today(),
            }
            self._insert_uid(data, user_id)
            self._client.table("streaks").insert(data).execute()


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
        # Migration: add name column if missing (existing DBs)
        try:
            self._conn.execute("SELECT name FROM scripts LIMIT 1")
        except sqlite3.OperationalError:
            self._conn.execute("ALTER TABLE scripts ADD COLUMN name TEXT DEFAULT ''")
        try:
            self._conn.execute("SELECT trigger_json FROM scripts LIMIT 1")
        except sqlite3.OperationalError:
            self._conn.execute("ALTER TABLE scripts ADD COLUMN trigger_json TEXT DEFAULT ''")
        self._conn.commit()

    def _execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        with self._lock:
            assert self._conn is not None
            cur = self._conn.execute(sql, params)
            self._conn.commit()
            return cur

    def _fetchall(self, sql: str, params: tuple = ()) -> list[dict]:
        with self._lock:
            assert self._conn is not None
            cur = self._conn.execute(sql, params)
            return [dict(row) for row in cur.fetchall()]

    def _fetchone(self, sql: str, params: tuple = ()) -> dict | None:
        with self._lock:
            assert self._conn is not None
            cur = self._conn.execute(sql, params)
            row = cur.fetchone()
            return dict(row) if row else None

    # -- Scripts --------------------------------------------------------
    def save_script(
        self,
        dsl_text: str,
        compiled_python: str,
        user_id: str = "local",
        name: str = "",
        trigger: dict | None = None,
    ) -> dict:
        cur = self._execute(
            "INSERT INTO scripts (user_id, name, dsl_text, compiled_python, trigger_json, created_at) VALUES (?,?,?,?,?,?)",
            (user_id, name, dsl_text, compiled_python, json.dumps(trigger, ensure_ascii=False) if trigger else "", _now()),
        )
        return self.get_script_by_id(cur.lastrowid)

    def get_scripts(self, user_id: str = "local") -> list[dict]:
        return self._fetchall(
            "SELECT * FROM scripts WHERE active = 1 AND user_id = ? ORDER BY id",
            (user_id,),
        )

    def get_script_by_id(self, script_id: int | None) -> dict:
        row = self._fetchone("SELECT * FROM scripts WHERE id = ?", (script_id,))
        if row is None:
            raise RuntimeError(f"スクリプト {script_id} が見つかりません")
        return row

    def update_script(self, script_id: int, **kwargs: Any) -> None:
        sets = ", ".join(f"{k} = ?" for k in kwargs)
        vals = tuple(kwargs.values()) + (script_id,)
        self._execute(f"UPDATE scripts SET {sets} WHERE id = ?", vals)

    def delete_script(self, script_id: int) -> None:
        self._execute("UPDATE scripts SET active = 0 WHERE id = ?", (script_id,))

    # -- Calendar Events ------------------------------------------------
    def add_event(
        self,
        title: str,
        start_at: str,
        end_at: str | None = None,
        note: str = "",
        source: str = "user",
        user_id: str = "local",
    ) -> dict:
        cur = self._execute(
            """INSERT INTO calendar_events (user_id, title, start_at, end_at, note, source, created_at)
               VALUES (?,?,?,?,?,?,?)""",
            (user_id, title, start_at, end_at, note, source, _now()),
        )
        row = self._fetchone("SELECT * FROM calendar_events WHERE id = ?", (cur.lastrowid,))
        return row  # type: ignore[return-value]

    def get_events(
        self,
        user_id: str = "local",
        keyword: str | None = None,
        start_from: str | None = None,
        start_to: str | None = None,
    ) -> list[dict]:
        sql = "SELECT * FROM calendar_events WHERE user_id = ?"
        params: list[Any] = [user_id]
        if keyword:
            sql += " AND title LIKE ?"
            params.append(f"%{keyword}%")
        if start_from:
            sql += " AND start_at >= ?"
            params.append(start_from)
        if start_to:
            sql += " AND start_at <= ?"
            params.append(start_to)
        sql += " ORDER BY start_at"
        return self._fetchall(sql, tuple(params))

    def delete_event(self, event_id: int) -> None:
        self._execute("DELETE FROM calendar_events WHERE id = ?", (event_id,))

    def update_event(self, event_id: int, **kwargs: Any) -> None:
        sets = ", ".join(f"{k} = ?" for k in kwargs)
        vals = tuple(kwargs.values()) + (event_id,)
        self._execute(f"UPDATE calendar_events SET {sets} WHERE id = ?", vals)

    # -- Machine Logs ---------------------------------------------------
    def add_machine_log(
        self,
        action_type: str,
        content: str,
        user_id: str = "local",
    ) -> dict:
        cur = self._execute(
            "INSERT INTO machine_logs (user_id, action_type, content, triggered_at) VALUES (?,?,?,?)",
            (user_id, action_type, content, _now()),
        )
        row = self._fetchone("SELECT * FROM machine_logs WHERE id = ?", (cur.lastrowid,))
        return row  # type: ignore[return-value]

    def get_machine_logs(self, user_id: str = "local", limit: int = 50) -> list[dict]:
        return self._fetchall(
            "SELECT * FROM machine_logs WHERE user_id = ? ORDER BY id DESC LIMIT ?",
            (user_id, limit),
        )

    def delete_machine_log(self, log_id: int) -> None:
        self._execute("DELETE FROM machine_logs WHERE id = ?", (log_id,))

    # -- Streaks --------------------------------------------------------
    def get_streak(self, habit_name: str, user_id: str = "local") -> int:
        row = self._fetchone(
            "SELECT count FROM streaks WHERE user_id = ? AND habit_name = ?",
            (user_id, habit_name),
        )
        return row["count"] if row else 0

    def update_streak(self, habit_name: str, count: int, user_id: str = "local") -> None:
        row = self._fetchone(
            "SELECT id FROM streaks WHERE user_id = ? AND habit_name = ?",
            (user_id, habit_name),
        )
        if row:
            self._execute(
                "UPDATE streaks SET count = ?, last_date = ? WHERE id = ?",
                (count, _today(), row["id"]),
            )
        else:
            self._execute(
                "INSERT INTO streaks (user_id, habit_name, count, last_date) VALUES (?,?,?,?)",
                (user_id, habit_name, count, _today()),
            )


# ======================================================================
# Unified DatabaseClient facade
# ======================================================================
class DatabaseClient:
    """統一 DB インターフェース。Supabase を試行し、失敗時は SQLite にフォールバック。

    ログイン後に set_user_id() を呼ぶと、以降の全クエリがそのユーザーに紐づく。
    """

    def __init__(self) -> None:
        self._backend: _SupabaseBackend | _SQLiteBackend | None = None
        self._is_supabase = False
        self._user_id: str = "local"

    def set_user_id(self, user_id: str) -> None:
        """ログインユーザーのIDをセットする。以降の全操作がこのIDで行われる。"""
        self._user_id = user_id or "local"

    @property
    def user_id(self) -> str:
        return self._user_id

    def connect(self) -> None:
        url = os.getenv("SUPABASE_URL", "")
        key = os.getenv("SUPABASE_ANON_KEY", "")
        if url and key:
            try:
                self._backend = _SupabaseBackend(url, key)
                self._is_supabase = True
                return
            except Exception:
                pass
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

    def _b(self) -> _SupabaseBackend | _SQLiteBackend:
        assert self._backend is not None, "DB未接続です。connect()を先に呼んでください。"
        return self._backend

    def _uid(self) -> str:
        return self._user_id

    # Scripts
    def save_script(
        self,
        dsl_text: str,
        compiled_python: str,
        user_id: str = "",
        name: str = "",
        trigger: dict | None = None,
    ) -> dict:
        return self._b().save_script(dsl_text, compiled_python, user_id or self._uid(), name, trigger)

    def get_scripts(self, user_id: str = "") -> list[dict]:
        return self._b().get_scripts(user_id or self._uid())

    def get_script_by_id(self, script_id: int) -> dict:
        return self._b().get_script_by_id(script_id)

    def update_script(self, script_id: int, **kwargs: Any) -> None:
        self._b().update_script(script_id, **kwargs)

    def delete_script(self, script_id: int) -> None:
        self._b().delete_script(script_id)

    # Calendar Events
    def add_event(self, **kwargs: Any) -> dict:
        if "user_id" not in kwargs or not kwargs["user_id"]:
            kwargs["user_id"] = self._uid()
        return self._b().add_event(**kwargs)

    def get_events(self, **kwargs: Any) -> list[dict]:
        if "user_id" not in kwargs or not kwargs["user_id"]:
            kwargs["user_id"] = self._uid()
        return self._b().get_events(**kwargs)

    def delete_event(self, event_id: int) -> None:
        self._b().delete_event(event_id)

    def update_event(self, event_id: int, **kwargs: Any) -> None:
        self._b().update_event(event_id, **kwargs)

    # Machine Logs
    def add_machine_log(self, action_type: str, content: str, user_id: str = "") -> dict:
        return self._b().add_machine_log(action_type, content, user_id or self._uid())

    def get_machine_logs(self, user_id: str = "", limit: int = 50) -> list[dict]:
        return self._b().get_machine_logs(user_id or self._uid(), limit)

    def delete_machine_log(self, log_id: int) -> None:
        self._b().delete_machine_log(log_id)

    # Streaks
    def get_streak(self, habit_name: str, user_id: str = "") -> int:
        return self._b().get_streak(habit_name, user_id or self._uid())

    def update_streak(self, habit_name: str, count: int, user_id: str = "") -> None:
        self._b().update_streak(habit_name, count, user_id or self._uid())


# Application-wide singleton
db_client = DatabaseClient()
