-- LifeScript Database Schema
-- Run this in the Supabase SQL Editor before first use.

CREATE TABLE IF NOT EXISTS rules (
  id            UUID         DEFAULT gen_random_uuid() PRIMARY KEY,
  title         TEXT         NOT NULL,
  lifescript_code TEXT       NOT NULL,
  compiled_python TEXT       NOT NULL,
  trigger_seconds INTEGER    NOT NULL DEFAULT 60,
  status        TEXT         NOT NULL DEFAULT 'active'
                             CHECK (status IN ('active', 'paused', 'deleted')),
  created_at    TIMESTAMPTZ  DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS logs (
  id            UUID         DEFAULT gen_random_uuid() PRIMARY KEY,
  rule_id       UUID         REFERENCES rules(id) ON DELETE CASCADE,
  executed_at   TIMESTAMPTZ  DEFAULT NOW(),
  result        TEXT         NOT NULL CHECK (result IN ('success', 'error')),
  error_message TEXT
);

CREATE TABLE IF NOT EXISTS connections (
  id            UUID         DEFAULT gen_random_uuid() PRIMARY KEY,
  service_name  TEXT         NOT NULL UNIQUE,
  access_token  TEXT         NOT NULL,
  refresh_token TEXT         DEFAULT '',
  connected_at  TIMESTAMPTZ  DEFAULT NOW()
);
