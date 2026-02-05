import asyncpg
import os
from datetime import datetime
from bot.config import DATABASE_URL

_pool = None


async def get_pool():
    """Get or create connection pool."""
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            DATABASE_URL,
            min_size=1,
            max_size=10
        )
    return _pool


async def close_pool():
    """Close the connection pool."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


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

        now = datetime.now().isoformat()

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
