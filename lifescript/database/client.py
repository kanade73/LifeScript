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
    trigger_type    TEXT    NOT NULL DEFAULT 'interval',
    trigger_seconds INTEGER NOT NULL DEFAULT 60,
    cron_minute     TEXT    DEFAULT NULL,
    cron_hour       TEXT    DEFAULT NULL,
    cron_day_of_week TEXT   DEFAULT NULL,
    cron_day        TEXT    DEFAULT NULL,
    cron_month      TEXT    DEFAULT NULL,
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

# Migration: add columns that may not exist in older databases
_MIGRATIONS = [
    "ALTER TABLE rules ADD COLUMN trigger_type TEXT NOT NULL DEFAULT 'interval'",
    "ALTER TABLE rules ADD COLUMN cron_minute TEXT DEFAULT NULL",
    "ALTER TABLE rules ADD COLUMN cron_hour TEXT DEFAULT NULL",
    "ALTER TABLE rules ADD COLUMN cron_day_of_week TEXT DEFAULT NULL",
    "ALTER TABLE rules ADD COLUMN cron_day TEXT DEFAULT NULL",
    "ALTER TABLE rules ADD COLUMN cron_month TEXT DEFAULT NULL",
]


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
        self._run_migrations()

    def _run_migrations(self) -> None:
        """Apply schema migrations (ignore errors for already-applied ones)."""
        assert self._conn is not None
        for sql in _MIGRATIONS:
            try:
                self._conn.execute(sql)
            except sqlite3.OperationalError:
                pass  # Column already exists
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
        trigger_type: str = "interval",
        cron_fields: dict | None = None,
    ) -> dict:
        cron = cron_fields or {}
        cur = self._execute(
            """
            INSERT INTO rules (
                title, lifescript_code, compiled_python,
                trigger_type, trigger_seconds,
                cron_minute, cron_hour, cron_day_of_week, cron_day, cron_month,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                title,
                lifescript_code,
                compiled_python,
                trigger_type,
                trigger_seconds,
                cron.get("minute"),
                cron.get("hour"),
                cron.get("day_of_week"),
                cron.get("day"),
                cron.get("month"),
                self._now(),
            ),
        )
        return self.get_rule_by_id(cur.lastrowid)

    def get_rules(self, include_paused: bool = False) -> list[dict]:
        with self._lock:
            assert self._conn is not None
            if include_paused:
                cur = self._conn.execute(
                    "SELECT * FROM rules WHERE status IN ('active', 'paused') ORDER BY id"
                )
            else:
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
        self._execute(
            "UPDATE rules SET status = ? WHERE id = ?",
            (status, str(rule_id)),
        )

    def delete_rule(self, rule_id: str) -> None:
        self._execute(
            "UPDATE rules SET status = 'deleted' WHERE id = ?",
            (str(rule_id),),
        )

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

    def get_logs(self, rule_id: str | None = None, limit: int = 100) -> list[dict]:
        with self._lock:
            assert self._conn is not None
            if rule_id:
                cur = self._conn.execute(
                    "SELECT * FROM execution_logs WHERE rule_id = ? ORDER BY id DESC LIMIT ?",
                    (str(rule_id), limit),
                )
            else:
                cur = self._conn.execute(
                    "SELECT * FROM execution_logs ORDER BY id DESC LIMIT ?",
                    (limit,),
                )
            return [dict(row) for row in cur.fetchall()]

    def get_last_execution(self, rule_id: str) -> dict | None:
        with self._lock:
            assert self._conn is not None
            cur = self._conn.execute(
                "SELECT * FROM execution_logs WHERE rule_id = ? ORDER BY id DESC LIMIT 1",
                (str(rule_id),),
            )
            row = cur.fetchone()
            return dict(row) if row else None


# Application-wide singleton
db_client = DatabaseClient()
