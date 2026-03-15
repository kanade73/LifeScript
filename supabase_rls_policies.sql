-- LifeScript: RLS ポリシー + FK 制約修正
-- Supabase Dashboard → SQL Editor で実行してください。
--
-- 1. user_id の外部キー制約を外す（認証なしフェーズで NULL を許容）
-- 2. RLS ポリシーを設定（開発フェーズ: 全操作許可）
--
-- 本番移行時に auth.uid() ベースのポリシーに切り替えること。

-- ============================================================
-- 1. FK 制約を削除（user_id は NULL のまま使えるようにする）
-- ============================================================
DO $$
DECLARE
    r RECORD;
BEGIN
    FOR r IN (
        SELECT conname, conrelid::regclass AS table_name
        FROM pg_constraint
        WHERE confrelid = 'users'::regclass
          AND contype = 'f'
    ) LOOP
        EXECUTE format('ALTER TABLE %s DROP CONSTRAINT %I', r.table_name, r.conname);
        RAISE NOTICE 'Dropped FK % on %', r.conname, r.table_name;
    END LOOP;
END $$;

-- ============================================================
-- 2. RLS ポリシー（開発フェーズ: 全操作許可）
-- ============================================================
-- scripts
ALTER TABLE scripts ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "allow_all_scripts" ON scripts;
CREATE POLICY "allow_all_scripts" ON scripts
  FOR ALL USING (true) WITH CHECK (true);

-- calendar_events
ALTER TABLE calendar_events ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "allow_all_calendar_events" ON calendar_events;
CREATE POLICY "allow_all_calendar_events" ON calendar_events
  FOR ALL USING (true) WITH CHECK (true);

-- machine_logs
ALTER TABLE machine_logs ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "allow_all_machine_logs" ON machine_logs;
CREATE POLICY "allow_all_machine_logs" ON machine_logs
  FOR ALL USING (true) WITH CHECK (true);

-- streaks
ALTER TABLE streaks ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "allow_all_streaks" ON streaks;
CREATE POLICY "allow_all_streaks" ON streaks
  FOR ALL USING (true) WITH CHECK (true);

-- users
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "allow_all_users" ON users;
CREATE POLICY "allow_all_users" ON users
  FOR ALL USING (true) WITH CHECK (true);
