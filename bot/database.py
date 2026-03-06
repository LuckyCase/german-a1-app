import asyncpg
import os
import ssl
import threading
import asyncio
from datetime import datetime
from bot.config import DATABASE_URL

# Thread-local storage for connection pools
# Each thread (gunicorn worker) gets its own pool
_local = threading.local()


def get_ssl_context():
    """Create SSL context for Supabase/cloud PostgreSQL connections."""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE  # Supabase uses self-signed certs
    return ctx


async def get_pool():
    """Get or create connection pool for current thread and event loop."""
    # Get current event loop
    try:
        current_loop = asyncio.get_running_loop()
    except RuntimeError:
        current_loop = None
    
    # Check if we have a pool for this thread
    if not hasattr(_local, 'pools'):
        _local.pools = {}
    
    # Use loop id as key (or thread id if no loop)
    pool_key = id(current_loop) if current_loop else threading.get_ident()
    
    # Check if pool exists and is valid
    if pool_key in _local.pools:
        pool = _local.pools[pool_key]
        # Check if pool is still valid (not closed)
        try:
            if not pool.is_closing():
                return pool
        except:
            pass
        # Pool is invalid, remove it
        del _local.pools[pool_key]
    
    # Create new pool
    if not DATABASE_URL:
        raise ValueError("DATABASE_URL is not set! Please configure database connection.")
    
    # Determine if we need SSL (for cloud databases like Supabase, Neon, etc.)
    use_ssl = 'supabase' in DATABASE_URL or 'neon' in DATABASE_URL or 'render' in DATABASE_URL
    
    pool = await asyncpg.create_pool(
        DATABASE_URL,
        min_size=1,
        max_size=5,  # Reduced for free tier limits
        command_timeout=60,
        ssl=get_ssl_context() if use_ssl else None,
        # For PgBouncer/Supabase pooler - disable prepared statements
        statement_cache_size=0 if 'pooler.supabase' in DATABASE_URL else 100
    )
    _local.pools[pool_key] = pool
    return pool


async def close_pool():
    """Close all connection pools for current thread."""
    if hasattr(_local, 'pools'):
        for pool in _local.pools.values():
            try:
                if not pool.is_closing():
                    await pool.close()
            except:
                pass
        _local.pools = {}


async def init_db():
    """Initialize database with required tables."""
    pool = await get_pool()

    async with pool.acquire() as conn:
        # Users table
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

        # User progress table
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

        # Grammar test results
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

        # Daily stats
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

        # Phrases progress
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

        # Dialogues progress
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

        # Add UNIQUE index for dialogues_progress (safe migration)
        await conn.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS uniq_dialogues_progress_user_dialogue
                ON dialogues_progress(user_id, dialogue_id)
        """)

        # Culture progress
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

        # Exercises progress
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

        # Feedback / suggestions table
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

        # Schema migrations (safe to run repeatedly)
        await conn.execute("""
            ALTER TABLE progress ADD COLUMN IF NOT EXISTS last_wrong_at TIMESTAMP
        """)
        await conn.execute("""
            ALTER TABLE phrases_progress ADD COLUMN IF NOT EXISTS wrong_count INTEGER DEFAULT 0
        """)
        await conn.execute("""
            ALTER TABLE phrases_progress ADD COLUMN IF NOT EXISTS last_wrong_at TIMESTAMP
        """)

        # Per-user level (persistent)
        await conn.execute("""
            ALTER TABLE users ADD COLUMN IF NOT EXISTS major_level TEXT DEFAULT 'A1'
        """)
        await conn.execute("""
            ALTER TABLE users ADD COLUMN IF NOT EXISTS sub_level TEXT DEFAULT '1'
        """)

        # Remove unused column
        await conn.execute("""
            ALTER TABLE progress DROP COLUMN IF EXISTS next_review
        """)

        # Deduplicate and add UNIQUE indexes (only if indexes don't exist yet)
        idx_exists = await conn.fetchval("""
            SELECT 1 FROM pg_indexes WHERE indexname = 'uniq_progress_user_word'
        """)
        if not idx_exists:
            # Deduplicate progress rows (merge counts into the row with MAX id, then delete extras)
            await conn.execute("""
                UPDATE progress p
                SET correct_count = k.cc,
                    wrong_count   = k.wc,
                    last_reviewed = k.lr,
                    last_wrong_at = k.lw
                FROM (
                    SELECT MAX(id) AS id, user_id, word_id,
                           SUM(correct_count) AS cc,
                           SUM(wrong_count)   AS wc,
                           MAX(last_reviewed) AS lr,
                           MAX(last_wrong_at) AS lw
                    FROM progress
                    GROUP BY user_id, word_id
                    HAVING COUNT(*) > 1
                ) k
                WHERE p.id = k.id
            """)
            await conn.execute("""
                DELETE FROM progress p1
                WHERE EXISTS (
                    SELECT 1 FROM progress p2
                    WHERE p2.user_id = p1.user_id
                      AND p2.word_id = p1.word_id
                      AND p2.id > p1.id
                )
            """)

            # Deduplicate phrases_progress rows
            await conn.execute("""
                UPDATE phrases_progress p
                SET correct_count = k.cc,
                    wrong_count   = k.wc,
                    last_reviewed = k.lr,
                    last_wrong_at = k.lw
                FROM (
                    SELECT MAX(id) AS id, user_id, phrase_id,
                           SUM(correct_count) AS cc,
                           SUM(wrong_count)   AS wc,
                           MAX(last_reviewed) AS lr,
                           MAX(last_wrong_at) AS lw
                    FROM phrases_progress
                    GROUP BY user_id, phrase_id
                    HAVING COUNT(*) > 1
                ) k
                WHERE p.id = k.id
            """)
            await conn.execute("""
                DELETE FROM phrases_progress p1
                WHERE EXISTS (
                    SELECT 1 FROM phrases_progress p2
                    WHERE p2.user_id = p1.user_id
                      AND p2.phrase_id = p1.phrase_id
                      AND p2.id > p1.id
                )
            """)

            # Add UNIQUE indexes
            await conn.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS uniq_progress_user_word
                    ON progress(user_id, word_id)
            """)
            await conn.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS uniq_phrases_progress_user_phrase
                    ON phrases_progress(user_id, phrase_id)
            """)


async def get_or_create_user(user_id: int, username: str = None, first_name: str = None):
    """Get existing user or create new one."""
    pool = await get_pool()

    async with pool.acquire() as conn:
        user = await conn.fetchrow(
            "SELECT * FROM users WHERE user_id = $1", user_id
        )

        if not user:
            await conn.execute(
                "INSERT INTO users (user_id, username, first_name) VALUES ($1, $2, $3)",
                user_id, username, first_name
            )
            user = await conn.fetchrow(
                "SELECT * FROM users WHERE user_id = $1", user_id
            )

        return user


async def update_word_progress(user_id: int, word_id: str, is_correct: bool):
    """Update user's progress for a specific word (atomic upsert)."""
    await get_or_create_user(user_id, None, None)
    pool = await get_pool()
    now = datetime.now()

    async with pool.acquire() as conn:
        if is_correct:
            await conn.execute(
                """INSERT INTO progress
                       (user_id, word_id, correct_count, wrong_count, last_reviewed, last_wrong_at)
                   VALUES ($1, $2, 1, 0, $3, NULL)
                   ON CONFLICT (user_id, word_id) DO UPDATE
                   SET correct_count = progress.correct_count + 1,
                       wrong_count   = GREATEST(progress.wrong_count - 1, 0),
                       last_reviewed = EXCLUDED.last_reviewed""",
                user_id, word_id, now
            )
        else:
            await conn.execute(
                """INSERT INTO progress
                       (user_id, word_id, correct_count, wrong_count, last_reviewed, last_wrong_at)
                   VALUES ($1, $2, 0, 1, $3, $3)
                   ON CONFLICT (user_id, word_id) DO UPDATE
                   SET wrong_count   = progress.wrong_count + 1,
                       last_reviewed = EXCLUDED.last_reviewed,
                       last_wrong_at = EXCLUDED.last_wrong_at""",
                user_id, word_id, now
            )


async def get_user_stats(user_id: int) -> dict:
    """Get user's learning statistics."""
    pool = await get_pool()

    async with pool.acquire() as conn:
        # Total words stats
        word_stats = await conn.fetchrow(
            """SELECT
                   COUNT(*) as total_words,
                   COALESCE(SUM(correct_count), 0) as total_correct,
                   COALESCE(SUM(wrong_count), 0) as total_wrong
               FROM progress WHERE user_id = $1""",
            user_id
        )

        # Grammar tests stats
        grammar_stats = await conn.fetchrow(
            """SELECT
                   COUNT(*) as tests_count,
                   COALESCE(SUM(score), 0) as total_score,
                   COALESCE(SUM(total), 0) as total_questions
               FROM grammar_results WHERE user_id = $1""",
            user_id
        )

        # Mastered words (correct >= 3, no wrong in last 3)
        mastered = await conn.fetchrow(
            """SELECT COUNT(*) as count FROM progress
               WHERE user_id = $1 AND correct_count >= 3 AND wrong_count = 0""",
            user_id
        )

        # Words with errors (need review)
        words_with_errors = await conn.fetchrow(
            """SELECT COUNT(*) as count FROM progress
               WHERE user_id = $1 AND wrong_count > 0""",
            user_id
        )

        # Phrases with errors (need review)
        phrases_with_errors = await conn.fetchrow(
            """SELECT COUNT(*) as count FROM phrases_progress
               WHERE user_id = $1 AND wrong_count > 0""",
            user_id
        )

        return {
            "total_words": word_stats["total_words"] or 0,
            "total_correct": word_stats["total_correct"] or 0,
            "total_wrong": word_stats["total_wrong"] or 0,
            "tests_completed": grammar_stats["tests_count"] or 0,
            "grammar_score": grammar_stats["total_score"] or 0,
            "grammar_total": grammar_stats["total_questions"] or 0,
            "mastered_words": mastered["count"] or 0,
            "words_with_errors": words_with_errors["count"] or 0,
            "phrases_with_errors": phrases_with_errors["count"] or 0
        }


async def get_detailed_user_progress(user_id: int) -> dict:
    """Get all progress data for a user across all content types."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        word_rows = await conn.fetch(
            "SELECT word_id, correct_count, wrong_count FROM progress WHERE user_id = $1",
            user_id
        )
        phrase_rows = await conn.fetch(
            "SELECT phrase_id, category_id, correct_count, wrong_count FROM phrases_progress WHERE user_id = $1",
            user_id
        )
        grammar_rows = await conn.fetch(
            "SELECT test_id, score, total, completed_at FROM grammar_results WHERE user_id = $1 ORDER BY completed_at DESC",
            user_id
        )
        dialogue_rows = await conn.fetch(
            "SELECT dialogue_id, exercises_completed, exercises_correct FROM dialogues_progress WHERE user_id = $1",
            user_id
        )
        culture_rows = await conn.fetch(
            "SELECT topic_id, quiz_completed, quiz_correct, quiz_total FROM culture_progress WHERE user_id = $1",
            user_id
        )
        exercise_rows = await conn.fetch(
            "SELECT set_id, tasks_completed, tasks_correct FROM exercises_progress WHERE user_id = $1",
            user_id
        )
    return {
        'words': [dict(r) for r in word_rows],
        'phrases': [dict(r) for r in phrase_rows],
        'grammar': [dict(r) for r in grammar_rows],
        'dialogues': [dict(r) for r in dialogue_rows],
        'culture': [dict(r) for r in culture_rows],
        'exercises': [dict(r) for r in exercise_rows],
    }


async def save_grammar_result(user_id: int, test_id: str, score: int, total: int):
    """Save grammar test result."""
    # Ensure user exists in database
    await get_or_create_user(user_id, None, None)
    
    pool = await get_pool()

    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO grammar_results (user_id, test_id, score, total) VALUES ($1, $2, $3, $4)",
            user_id, test_id, score, total
        )


async def update_daily_stats(user_id: int, words: int = 0, tests: int = 0, correct: int = 0, total: int = 0):
    """Update daily statistics for user."""
    import logging
    logger = logging.getLogger(__name__)
    
    # Ensure user exists in database
    await get_or_create_user(user_id, None, None)
    
    today = datetime.now().strftime("%Y-%m-%d")
    pool = await get_pool()

    try:
        async with pool.acquire() as conn:
            # Use UPSERT (INSERT ... ON CONFLICT) for atomic operation
            await conn.execute(
                """INSERT INTO daily_stats (user_id, date, words_learned, tests_completed, correct_answers, total_answers)
                   VALUES ($1, $2, $3, $4, $5, $6)
                   ON CONFLICT (user_id, date) DO UPDATE
                   SET words_learned = daily_stats.words_learned + $3,
                       tests_completed = daily_stats.tests_completed + $4,
                       correct_answers = daily_stats.correct_answers + $5,
                       total_answers = daily_stats.total_answers + $6""",
                user_id, today, words, tests, correct, total
            )
    except Exception as e:
        logger.error(f"Error updating daily stats for user {user_id}: {e}", exc_info=True)
        raise


async def get_users_for_reminder(hour: int, minute: int) -> list:
    """Get users who should receive reminder at given time."""
    pool = await get_pool()

    async with pool.acquire() as conn:
        users = await conn.fetch(
            """SELECT user_id FROM users
               WHERE reminder_enabled = 1 AND reminder_hour = $1 AND reminder_minute = $2""",
            hour, minute
        )
        return [u["user_id"] for u in users]


async def set_reminder(user_id: int, enabled: bool, hour: int = 9, minute: int = 0):
    """Set reminder settings for user."""
    # Ensure user exists in database
    await get_or_create_user(user_id, None, None)
    
    pool = await get_pool()

    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE users SET reminder_enabled = $1, reminder_hour = $2, reminder_minute = $3 WHERE user_id = $4",
            1 if enabled else 0, hour, minute, user_id
        )


async def save_phrase_progress(user_id: int, phrase_id: str, category_id: str, is_correct: bool):
    """Save phrase progress for user (atomic upsert)."""
    await get_or_create_user(user_id, None, None)
    pool = await get_pool()
    now = datetime.now()

    async with pool.acquire() as conn:
        if is_correct:
            await conn.execute(
                """INSERT INTO phrases_progress
                       (user_id, phrase_id, category_id, correct_count, wrong_count, last_reviewed, last_wrong_at)
                   VALUES ($1, $2, $3, 1, 0, $4, NULL)
                   ON CONFLICT (user_id, phrase_id) DO UPDATE
                   SET correct_count = phrases_progress.correct_count + 1,
                       wrong_count   = GREATEST(phrases_progress.wrong_count - 1, 0),
                       last_reviewed = EXCLUDED.last_reviewed""",
                user_id, phrase_id, category_id, now
            )
        else:
            await conn.execute(
                """INSERT INTO phrases_progress
                       (user_id, phrase_id, category_id, correct_count, wrong_count, last_reviewed, last_wrong_at)
                   VALUES ($1, $2, $3, 0, 1, $4, $4)
                   ON CONFLICT (user_id, phrase_id) DO UPDATE
                   SET wrong_count   = phrases_progress.wrong_count + 1,
                       last_reviewed = EXCLUDED.last_reviewed,
                       last_wrong_at = EXCLUDED.last_wrong_at""",
                user_id, phrase_id, category_id, now
            )


async def save_dialogue_progress(user_id: int, dialogue_id: str, exercises_completed: int, exercises_correct: int):
    """Save dialogue progress for user (atomic upsert)."""
    await get_or_create_user(user_id, None, None)
    pool = await get_pool()
    now = datetime.now()

    async with pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO dialogues_progress
                   (user_id, dialogue_id, exercises_completed, exercises_correct, completed_at)
               VALUES ($1, $2, $3, $4, $5)
               ON CONFLICT (user_id, dialogue_id) DO UPDATE
               SET exercises_completed = dialogues_progress.exercises_completed + EXCLUDED.exercises_completed,
                   exercises_correct = dialogues_progress.exercises_correct + EXCLUDED.exercises_correct,
                   completed_at = EXCLUDED.completed_at""",
            user_id, dialogue_id, exercises_completed, exercises_correct, now
        )


async def save_culture_progress(
    user_id: int,
    topic_id: str,
    major: str,
    sub: str,
    viewed_at=None,
    quiz_completed: int = 0,
    quiz_correct: int = 0,
    quiz_total: int = 0,
):
    """Save or update culture topic progress for user (upsert by user_id, topic_id, major, sub)."""
    await get_or_create_user(user_id, None, None)
    pool = await get_pool()
    now = datetime.now()
    viewed = viewed_at or now

    async with pool.acquire() as conn:
        existing = await conn.fetchrow(
            """SELECT id, viewed_at, quiz_completed FROM culture_progress
               WHERE user_id = $1 AND topic_id = $2 AND major_level = $3 AND sub_level = $4""",
            user_id, topic_id, major, sub
        )
        if existing:
            # Update: set viewed_at if not yet set; update quiz only if new result is better
            await conn.execute(
                """UPDATE culture_progress
                   SET viewed_at = COALESCE(culture_progress.viewed_at, $1),
                       quiz_completed = GREATEST(culture_progress.quiz_completed, $2),
                       quiz_correct = CASE WHEN $2 > culture_progress.quiz_completed THEN $3 ELSE culture_progress.quiz_correct END,
                       quiz_total = CASE WHEN $2 > culture_progress.quiz_completed THEN $4 ELSE culture_progress.quiz_total END
                   WHERE user_id = $5 AND topic_id = $6 AND major_level = $7 AND sub_level = $8""",
                viewed, quiz_completed, quiz_correct, quiz_total,
                user_id, topic_id, major, sub
            )
        else:
            await conn.execute(
                """INSERT INTO culture_progress
                   (user_id, topic_id, major_level, sub_level, viewed_at, quiz_completed, quiz_correct, quiz_total)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8)""",
                user_id, topic_id, major, sub, viewed, quiz_completed, quiz_correct, quiz_total
            )


async def save_exercise_set_progress(
    user_id: int,
    set_id: str,
    major: str,
    sub: str,
    tasks_completed: int,
    tasks_correct: int,
):
    """Save or update exercise set progress for user (upsert by user_id, set_id, major, sub)."""
    await get_or_create_user(user_id, None, None)
    pool = await get_pool()
    now = datetime.now()

    async with pool.acquire() as conn:
        existing = await conn.fetchrow(
            """SELECT id FROM exercises_progress
               WHERE user_id = $1 AND set_id = $2 AND major_level = $3 AND sub_level = $4""",
            user_id, set_id, major, sub
        )
        if existing:
            await conn.execute(
                """UPDATE exercises_progress
                   SET tasks_completed = $1, tasks_correct = $2, completed_at = $3
                   WHERE user_id = $4 AND set_id = $5 AND major_level = $6 AND sub_level = $7""",
                tasks_completed, tasks_correct, now, user_id, set_id, major, sub
            )
        else:
            await conn.execute(
                """INSERT INTO exercises_progress
                   (user_id, set_id, major_level, sub_level, tasks_completed, tasks_correct, completed_at)
                   VALUES ($1, $2, $3, $4, $5, $6, $7)""",
                user_id, set_id, major, sub, tasks_completed, tasks_correct, now
            )


# Feedback status codes:
# 0 - Новый (по умолчанию)
# 1 - Просмотрен
# 2 - Принято к рассмотрению
# 3 - В работе
# 4 - Выполнено
# 5 - Отклонено

FEEDBACK_STATUS_LABELS = {
    0: "📝 Отправлено",
    1: "👀 Просмотрено",
    2: "✅ Принято",
    3: "🔧 В работе",
    4: "🎉 Готово!",
    5: "❌ Отклонено"
}

MAX_FEEDBACK_LENGTH = 1000


async def save_feedback(user_id: int, text: str) -> int:
    """Save user feedback/suggestion. Returns the feedback id."""
    # Ensure user exists in database
    await get_or_create_user(user_id, None, None)
    
    pool = await get_pool()
    now = datetime.now()

    async with pool.acquire() as conn:
        result = await conn.fetchrow(
            """INSERT INTO feedback (user_id, text, status, created_at, updated_at)
               VALUES ($1, $2, 0, $3, $3)
               RETURNING id""",
            user_id, text[:MAX_FEEDBACK_LENGTH], now
        )
        return result["id"]


async def get_user_feedback(user_id: int, limit: int = 10) -> list:
    """Get user's feedback/suggestions ordered by date (newest first)."""
    pool = await get_pool()

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT id, text, status, created_at, updated_at
               FROM feedback
               WHERE user_id = $1
               ORDER BY created_at DESC
               LIMIT $2""",
            user_id, limit
        )
        return [dict(row) for row in rows]


async def get_feedback_count(user_id: int) -> int:
    """Get total count of user's feedback."""
    pool = await get_pool()

    async with pool.acquire() as conn:
        result = await conn.fetchrow(
            "SELECT COUNT(*) as count FROM feedback WHERE user_id = $1",
            user_id
        )
        return result["count"]


async def get_priority_word_ids(user_id: int, word_ids: list) -> list:
    """Get word_ids from the given list that have errors, sorted by priority (most errors first)."""
    if not word_ids:
        return []
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT word_id, wrong_count, last_wrong_at
               FROM progress
               WHERE user_id = $1 AND word_id = ANY($2) AND wrong_count > 0
               ORDER BY wrong_count DESC, last_wrong_at DESC NULLS LAST""",
            user_id, word_ids
        )
        return [row["word_id"] for row in rows]


async def get_all_error_word_ids(user_id: int) -> list:
    """Get all word_ids with errors for the user, sorted by priority."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT word_id
               FROM progress
               WHERE user_id = $1 AND wrong_count > 0
               ORDER BY wrong_count DESC, last_wrong_at DESC NULLS LAST""",
            user_id
        )
        return [row["word_id"] for row in rows]


async def get_priority_phrase_ids(user_id: int, phrase_ids: list) -> list:
    """Get phrase_ids from the given list that have errors, sorted by priority."""
    if not phrase_ids:
        return []
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT phrase_id, wrong_count, last_wrong_at
               FROM phrases_progress
               WHERE user_id = $1 AND phrase_id = ANY($2) AND wrong_count > 0
               ORDER BY wrong_count DESC, last_wrong_at DESC NULLS LAST""",
            user_id, phrase_ids
        )
        return [row["phrase_id"] for row in rows]


async def get_all_error_phrase_ids(user_id: int) -> list:
    """Get all phrase_ids with errors for the user, sorted by priority."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT phrase_id
               FROM phrases_progress
               WHERE user_id = $1 AND wrong_count > 0
               ORDER BY wrong_count DESC, last_wrong_at DESC NULLS LAST""",
            user_id
        )
        return [row["phrase_id"] for row in rows]


# ============================================================
# Settings: user preferences
# ============================================================

async def get_user_settings(user_id: int) -> dict:
    """Get user settings (level, reminders)."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """SELECT reminder_enabled, reminder_hour, reminder_minute,
                      major_level, sub_level
               FROM users WHERE user_id = $1""",
            user_id
        )
        if not row:
            return {
                "reminder_enabled": 1,
                "reminder_hour": 9,
                "reminder_minute": 0,
                "major_level": "A1",
                "sub_level": "1",
            }
        return dict(row)


async def set_user_level(user_id: int, major: str, sub: str):
    """Persist user's chosen level."""
    await get_or_create_user(user_id, None, None)
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE users SET major_level = $1, sub_level = $2 WHERE user_id = $3",
            major, sub, user_id
        )


async def reset_user_progress(user_id: int):
    """Delete ALL learning progress for user (irreversible)."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM progress WHERE user_id = $1", user_id)
        await conn.execute("DELETE FROM phrases_progress WHERE user_id = $1", user_id)
        await conn.execute("DELETE FROM grammar_results WHERE user_id = $1", user_id)
        await conn.execute("DELETE FROM daily_stats WHERE user_id = $1", user_id)
        await conn.execute("DELETE FROM dialogues_progress WHERE user_id = $1", user_id)
        await conn.execute("DELETE FROM culture_progress WHERE user_id = $1", user_id)
        await conn.execute("DELETE FROM exercises_progress WHERE user_id = $1", user_id)
