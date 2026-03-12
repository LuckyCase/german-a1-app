"""
Initial schema — all CREATE TABLE and ALTER TABLE statements
that were previously inside init_db().

This migration is idempotent (IF NOT EXISTS / IF NOT EXISTS everywhere).
"""


async def upgrade(conn) -> None:
    # ── Core tables ──────────────────────────────────────────────
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            reminder_enabled INTEGER DEFAULT 1,
            reminder_hour INTEGER DEFAULT 9,
            reminder_minute INTEGER DEFAULT 0
        )
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS progress (
            id SERIAL PRIMARY KEY,
            user_id BIGINT,
            word_id TEXT,
            correct_count INTEGER DEFAULT 0,
            wrong_count INTEGER DEFAULT 0,
            last_reviewed TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS grammar_results (
            id SERIAL PRIMARY KEY,
            user_id BIGINT,
            test_id TEXT,
            score INTEGER,
            total INTEGER,
            completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS daily_stats (
            id SERIAL PRIMARY KEY,
            user_id BIGINT,
            date TEXT,
            words_learned INTEGER DEFAULT 0,
            tests_completed INTEGER DEFAULT 0,
            correct_answers INTEGER DEFAULT 0,
            total_answers INTEGER DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users (user_id),
            UNIQUE(user_id, date)
        )
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS phrases_progress (
            id SERIAL PRIMARY KEY,
            user_id BIGINT,
            phrase_id TEXT,
            category_id TEXT,
            correct_count INTEGER DEFAULT 0,
            wrong_count INTEGER DEFAULT 0,
            last_reviewed TIMESTAMP,
            last_wrong_at TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS dialogues_progress (
            id SERIAL PRIMARY KEY,
            user_id BIGINT,
            dialogue_id TEXT,
            exercises_completed INTEGER DEFAULT 0,
            exercises_correct INTEGER DEFAULT 0,
            completed_at TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    """)

    await conn.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uniq_dialogues_progress_user_dialogue
            ON dialogues_progress(user_id, dialogue_id)
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS culture_progress (
            id SERIAL PRIMARY KEY,
            user_id BIGINT,
            topic_id TEXT,
            major_level TEXT NOT NULL,
            sub_level TEXT NOT NULL,
            viewed_at TIMESTAMP,
            quiz_completed INTEGER DEFAULT 0,
            quiz_correct INTEGER DEFAULT 0,
            quiz_total INTEGER DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users (user_id),
            UNIQUE(user_id, topic_id, major_level, sub_level)
        )
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS exercises_progress (
            id SERIAL PRIMARY KEY,
            user_id BIGINT,
            set_id TEXT,
            major_level TEXT NOT NULL,
            sub_level TEXT NOT NULL,
            tasks_completed INTEGER DEFAULT 0,
            tasks_correct INTEGER DEFAULT 0,
            completed_at TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (user_id),
            UNIQUE(user_id, set_id, major_level, sub_level)
        )
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS feedback (
            id SERIAL PRIMARY KEY,
            user_id BIGINT,
            text TEXT NOT NULL,
            status INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    """)

    # ── Column migrations ────────────────────────────────────────
    await conn.execute("ALTER TABLE progress ADD COLUMN IF NOT EXISTS last_wrong_at TIMESTAMP")
    await conn.execute("ALTER TABLE phrases_progress ADD COLUMN IF NOT EXISTS wrong_count INTEGER DEFAULT 0")
    await conn.execute("ALTER TABLE phrases_progress ADD COLUMN IF NOT EXISTS last_wrong_at TIMESTAMP")
    await conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS major_level TEXT DEFAULT 'A1'")
    await conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS sub_level TEXT DEFAULT '1'")
    await conn.execute("ALTER TABLE progress DROP COLUMN IF EXISTS next_review")

    # SRS columns
    await conn.execute("ALTER TABLE progress ADD COLUMN IF NOT EXISTS next_review_at TIMESTAMP")
    await conn.execute("ALTER TABLE progress ADD COLUMN IF NOT EXISTS srs_streak INTEGER DEFAULT 0")
    await conn.execute("ALTER TABLE phrases_progress ADD COLUMN IF NOT EXISTS next_review_at TIMESTAMP")
    await conn.execute("ALTER TABLE phrases_progress ADD COLUMN IF NOT EXISTS srs_streak INTEGER DEFAULT 0")

    # Streak & achievements
    await conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS last_active_date TEXT")
    await conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS current_streak INTEGER DEFAULT 0")
    await conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS achievements TEXT DEFAULT '[]'")

    # Diagnostic flag
    await conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS diagnostic_completed INTEGER DEFAULT 0")

    # ── One-time data backfills ──────────────────────────────────
    # SRS backfill for words
    srs_done = await conn.fetchval(
        "SELECT 1 FROM progress WHERE next_review_at IS NOT NULL LIMIT 1"
    )
    if not srs_done:
        await conn.execute("""
            UPDATE progress SET next_review_at = NOW(), srs_streak = 0
            WHERE wrong_count > 0 AND next_review_at IS NULL
        """)
        await conn.execute("""
            UPDATE progress SET next_review_at = NOW() + INTERVAL '7 days',
                   srs_streak = LEAST(correct_count, 5)
            WHERE correct_count >= 3 AND wrong_count = 0 AND next_review_at IS NULL
        """)
        await conn.execute("""
            UPDATE progress SET next_review_at = NOW(), srs_streak = 0
            WHERE next_review_at IS NULL AND last_reviewed IS NOT NULL
        """)

    # SRS backfill for phrases
    srs_phrases_done = await conn.fetchval(
        "SELECT 1 FROM phrases_progress WHERE next_review_at IS NOT NULL LIMIT 1"
    )
    if not srs_phrases_done:
        await conn.execute("""
            UPDATE phrases_progress SET next_review_at = NOW(), srs_streak = 0
            WHERE wrong_count > 0 AND next_review_at IS NULL
        """)
        await conn.execute("""
            UPDATE phrases_progress SET next_review_at = NOW() + INTERVAL '7 days',
                   srs_streak = LEAST(correct_count, 5)
            WHERE correct_count >= 3 AND wrong_count = 0 AND next_review_at IS NULL
        """)
        await conn.execute("""
            UPDATE phrases_progress SET next_review_at = NOW(), srs_streak = 0
            WHERE next_review_at IS NULL AND last_reviewed IS NOT NULL
        """)

    # Mark existing users as having completed diagnostic
    await conn.execute("""
        UPDATE users SET diagnostic_completed = 1
        WHERE diagnostic_completed IS NULL
           OR (diagnostic_completed = 0 AND last_active_date IS NOT NULL)
    """)

    # ── Deduplication & unique indexes ───────────────────────────
    idx_exists = await conn.fetchval(
        "SELECT 1 FROM pg_indexes WHERE indexname = 'uniq_progress_user_word'"
    )
    if not idx_exists:
        await conn.execute("""
            UPDATE progress p
            SET correct_count = k.cc, wrong_count = k.wc,
                last_reviewed = k.lr, last_wrong_at = k.lw
            FROM (
                SELECT MAX(id) AS id, user_id, word_id,
                       SUM(correct_count) AS cc, SUM(wrong_count) AS wc,
                       MAX(last_reviewed) AS lr, MAX(last_wrong_at) AS lw
                FROM progress GROUP BY user_id, word_id HAVING COUNT(*) > 1
            ) k WHERE p.id = k.id
        """)
        await conn.execute("""
            DELETE FROM progress p1
            WHERE EXISTS (
                SELECT 1 FROM progress p2
                WHERE p2.user_id = p1.user_id AND p2.word_id = p1.word_id AND p2.id > p1.id
            )
        """)
        await conn.execute("""
            UPDATE phrases_progress p
            SET correct_count = k.cc, wrong_count = k.wc,
                last_reviewed = k.lr, last_wrong_at = k.lw
            FROM (
                SELECT MAX(id) AS id, user_id, phrase_id,
                       SUM(correct_count) AS cc, SUM(wrong_count) AS wc,
                       MAX(last_reviewed) AS lr, MAX(last_wrong_at) AS lw
                FROM phrases_progress GROUP BY user_id, phrase_id HAVING COUNT(*) > 1
            ) k WHERE p.id = k.id
        """)
        await conn.execute("""
            DELETE FROM phrases_progress p1
            WHERE EXISTS (
                SELECT 1 FROM phrases_progress p2
                WHERE p2.user_id = p1.user_id AND p2.phrase_id = p1.phrase_id AND p2.id > p1.id
            )
        """)
        await conn.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS uniq_progress_user_word
                ON progress(user_id, word_id)
        """)
        await conn.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS uniq_phrases_progress_user_phrase
                ON phrases_progress(user_id, phrase_id)
        """)
