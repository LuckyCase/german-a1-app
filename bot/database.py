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
                next_review TIMESTAMP,
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
    """Update user's progress for a specific word."""
    pool = await get_pool()

    async with pool.acquire() as conn:
        existing = await conn.fetchrow(
            "SELECT * FROM progress WHERE user_id = $1 AND word_id = $2",
            user_id, word_id
        )

        now = datetime.now()

        if existing:
            if is_correct:
                await conn.execute(
                    """UPDATE progress
                       SET correct_count = correct_count + 1, last_reviewed = $1
                       WHERE user_id = $2 AND word_id = $3""",
                    now, user_id, word_id
                )
            else:
                await conn.execute(
                    """UPDATE progress
                       SET wrong_count = wrong_count + 1, last_reviewed = $1
                       WHERE user_id = $2 AND word_id = $3""",
                    now, user_id, word_id
                )
        else:
            correct = 1 if is_correct else 0
            wrong = 0 if is_correct else 1
            await conn.execute(
                """INSERT INTO progress (user_id, word_id, correct_count, wrong_count, last_reviewed)
                   VALUES ($1, $2, $3, $4, $5)""",
                user_id, word_id, correct, wrong, now
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

        return {
            "total_words": word_stats["total_words"] or 0,
            "total_correct": word_stats["total_correct"] or 0,
            "total_wrong": word_stats["total_wrong"] or 0,
            "tests_completed": grammar_stats["tests_count"] or 0,
            "grammar_score": grammar_stats["total_score"] or 0,
            "grammar_total": grammar_stats["total_questions"] or 0,
            "mastered_words": mastered["count"] or 0
        }


async def save_grammar_result(user_id: int, test_id: str, score: int, total: int):
    """Save grammar test result."""
    pool = await get_pool()

    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO grammar_results (user_id, test_id, score, total) VALUES ($1, $2, $3, $4)",
            user_id, test_id, score, total
        )


async def update_daily_stats(user_id: int, words: int = 0, tests: int = 0, correct: int = 0, total: int = 0):
    """Update daily statistics for user."""
    today = datetime.now().strftime("%Y-%m-%d")
    pool = await get_pool()

    async with pool.acquire() as conn:
        existing = await conn.fetchrow(
            "SELECT * FROM daily_stats WHERE user_id = $1 AND date = $2",
            user_id, today
        )

        if existing:
            await conn.execute(
                """UPDATE daily_stats
                   SET words_learned = words_learned + $1,
                       tests_completed = tests_completed + $2,
                       correct_answers = correct_answers + $3,
                       total_answers = total_answers + $4
                   WHERE user_id = $5 AND date = $6""",
                words, tests, correct, total, user_id, today
            )
        else:
            await conn.execute(
                """INSERT INTO daily_stats (user_id, date, words_learned, tests_completed, correct_answers, total_answers)
                   VALUES ($1, $2, $3, $4, $5, $6)""",
                user_id, today, words, tests, correct, total
            )


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
    pool = await get_pool()

    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE users SET reminder_enabled = $1, reminder_hour = $2, reminder_minute = $3 WHERE user_id = $4",
            1 if enabled else 0, hour, minute, user_id
        )
