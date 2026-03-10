-- LifeScript Database Schema
-- Used for both Supabase (PostgreSQL) and SQLite fallback

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
