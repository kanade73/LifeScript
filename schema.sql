-- LifeScript Database Schema (v2)
-- Supabase (PostgreSQL) 用。SQLiteフォールバックは database/client.py 内で定義。

CREATE TABLE IF NOT EXISTS users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           TEXT UNIQUE NOT NULL,
    personality_json JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS scripts (
    id              SERIAL PRIMARY KEY,
    user_id         UUID REFERENCES users(id),
    dsl_text        TEXT NOT NULL,
    compiled_python TEXT DEFAULT '',
    active          BOOLEAN DEFAULT true,
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS calendar_events (
    id              SERIAL PRIMARY KEY,
    user_id         UUID REFERENCES users(id),
    title           TEXT NOT NULL,
    start_at        TIMESTAMPTZ NOT NULL,
    end_at          TIMESTAMPTZ,
    note            TEXT DEFAULT '',
    source          TEXT NOT NULL DEFAULT 'user',
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS machine_logs (
    id              SERIAL PRIMARY KEY,
    user_id         UUID REFERENCES users(id),
    action_type     TEXT NOT NULL,
    content         TEXT NOT NULL DEFAULT '',
    triggered_at    TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS streaks (
    id              SERIAL PRIMARY KEY,
    user_id         UUID REFERENCES users(id),
    habit_name      TEXT NOT NULL,
    count           INTEGER DEFAULT 0,
    last_date       DATE
);
