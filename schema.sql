-- LifeScript Database Schema (SQLite)
-- Auto-applied on first launch at ~/.lifescript/lifescript.db

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
