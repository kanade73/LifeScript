"""SQLite database client - auto-created at ~/.lifescript/lifescript.db"""

from __future__ import annotations

import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

_DB_DIR = Path.home() / ".lifescript"
_DB_PATH = _DB_DIR / "lifescript.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS rules (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    title           TEXT    NOT NULL,
    lifescript_code TEXT    NOT NULL,
    compiled_python TEXT    NOT NULL,
    trigger_seconds INTEGER NOT NULL DEFAULT 60,
    status          TEXT    NOT NULL DEFAULT 'active',
    created_at      TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS connections (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    service_name  TEXT    NOT NULL UNIQUE,
    access_token  TEXT    NOT NULL,
    refresh_token TEXT    NOT NULL DEFAULT '',
    connected_at  TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS execution_logs (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_id    TEXT    NOT NULL,
    status     TEXT    NOT NULL,
    message    TEXT    NOT NULL DEFAULT '',
    created_at TEXT    NOT NULL
);
"""


class DatabaseClient:
    def __init__(self) -> None:
        self._conn: sqlite3.Connection | None = None
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------
    def connect(self) -> None:
        _DB_DIR.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(
            str(_DB_PATH),
            check_same_thread=False,
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    @property
    def is_connected(self) -> bool:
        return self._conn is not None

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        with self._lock:
            assert self._conn is not None
            cur = self._conn.execute(sql, params)
            self._conn.commit()
            return cur

    # ------------------------------------------------------------------
    # Rules
    # ------------------------------------------------------------------
    def save_rule(
        self,
        title: str,
        lifescript_code: str,
        compiled_python: str,
        trigger_seconds: int = 60,
    ) -> dict:
        cur = self._execute(
            """
            INSERT INTO rules (title, lifescript_code, compiled_python, trigger_seconds, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (title, lifescript_code, compiled_python, trigger_seconds, self._now()),
        )
        return self._get_rule_by_id(cur.lastrowid)

    def get_rules(self) -> list[dict]:
        with self._lock:
            assert self._conn is not None
            cur = self._conn.execute("SELECT * FROM rules WHERE status = 'active' ORDER BY id")
            return [dict(row) for row in cur.fetchall()]

    def update_rule_python(self, rule_id: str, compiled_python: str) -> None:
        self._execute(
            "UPDATE rules SET compiled_python = ? WHERE id = ?",
            (compiled_python, str(rule_id)),
        )

    def delete_rule(self, rule_id: str) -> None:
        self._execute(
            "UPDATE rules SET status = 'deleted' WHERE id = ?",
            (str(rule_id),),
        )

    def _get_rule_by_id(self, rule_id: int | None) -> dict:
        with self._lock:
            assert self._conn is not None
            cur = self._conn.execute("SELECT * FROM rules WHERE id = ?", (rule_id,))
            row = cur.fetchone()
            if row is None:
                raise RuntimeError(f"Rule {rule_id} not found after insert")
            return dict(row)

    # ------------------------------------------------------------------
    # Connections (LINE credentials etc.)
    # ------------------------------------------------------------------
    def get_connection(self, service_name: str) -> dict | None:
        with self._lock:
            assert self._conn is not None
            cur = self._conn.execute(
                "SELECT * FROM connections WHERE service_name = ?", (service_name,)
            )
            row = cur.fetchone()
            return dict(row) if row else None

    def save_connection(
        self, service_name: str, access_token: str, refresh_token: str = ""
    ) -> None:
        self._execute(
            """
            INSERT INTO connections (service_name, access_token, refresh_token, connected_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(service_name) DO UPDATE SET
                access_token  = excluded.access_token,
                refresh_token = excluded.refresh_token,
                connected_at  = excluded.connected_at
            """,
            (service_name, access_token, refresh_token, self._now()),
        )

    def delete_connection(self, service_name: str) -> None:
        self._execute("DELETE FROM connections WHERE service_name = ?", (service_name,))

    # ------------------------------------------------------------------
    # Execution logs
    # ------------------------------------------------------------------
    def save_log(self, rule_id: str, status: str, message: str = "") -> None:
        self._execute(
            """
            INSERT INTO execution_logs (rule_id, status, message, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (str(rule_id), status, message, self._now()),
        )


# Application-wide singleton
db_client = DatabaseClient()
