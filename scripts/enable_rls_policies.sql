-- Включаем RLS на всех таблицах (идемпотентно: повторный вызов не ломает)
ALTER TABLE daily_stats ENABLE ROW LEVEL SECURITY;
ALTER TABLE dialogues_progress ENABLE ROW LEVEL SECURITY;
ALTER TABLE feedback ENABLE ROW LEVEL SECURITY;
ALTER TABLE grammar_results ENABLE ROW LEVEL SECURITY;
ALTER TABLE phrases_progress ENABLE ROW LEVEL SECURITY;
ALTER TABLE progress ENABLE ROW LEVEL SECURITY;
ALTER TABLE users ENABLE ROW LEVEL SECURITY;

-- Политики: сначала DROP IF EXISTS, чтобы не падать на "already exists"
DROP POLICY IF EXISTS "Deny all direct access to users" ON daily_stats;
CREATE POLICY "Deny all direct access to users" ON daily_stats FOR ALL USING (false);

DROP POLICY IF EXISTS "Deny all direct access to users" ON dialogues_progress;
CREATE POLICY "Deny all direct access to users" ON dialogues_progress FOR ALL USING (false);

DROP POLICY IF EXISTS "Deny all direct access to users" ON feedback;
CREATE POLICY "Deny all direct access to users" ON feedback FOR ALL USING (false);

DROP POLICY IF EXISTS "Deny all direct access to users" ON grammar_results;
CREATE POLICY "Deny all direct access to users" ON grammar_results FOR ALL USING (false);

DROP POLICY IF EXISTS "Deny all direct access to users" ON phrases_progress;
CREATE POLICY "Deny all direct access to users" ON phrases_progress FOR ALL USING (false);

DROP POLICY IF EXISTS "Deny all direct access to users" ON progress;
CREATE POLICY "Deny all direct access to users" ON progress FOR ALL USING (false);

DROP POLICY IF EXISTS "Deny all direct access to users" ON users;
CREATE POLICY "Deny all direct access to users" ON users FOR ALL USING (false);
