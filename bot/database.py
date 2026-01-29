import aiosqlite
import os
from datetime import datetime
from bot.config import DATABASE_PATH


async def init_db():
    """Initialize database with required tables."""
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)

    async with aiosqlite.connect(DATABASE_PATH) as db:
        # Users table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                reminder_enabled INTEGER DEFAULT 1,
                reminder_hour INTEGER DEFAULT 9,
                reminder_minute INTEGER DEFAULT 0
            )
        """)

        # User progress table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS progress (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                word_id TEXT,
                correct_count INTEGER DEFAULT 0,
                wrong_count INTEGER DEFAULT 0,
                last_reviewed TIMESTAMP,
                next_review TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        """)

        # Grammar test results
        await db.execute("""
            CREATE TABLE IF NOT EXISTS grammar_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                test_id TEXT,
                score INTEGER,
                total INTEGER,
                completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        """)

        # Daily stats
        await db.execute("""
            CREATE TABLE IF NOT EXISTS daily_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                date TEXT,
                words_learned INTEGER DEFAULT 0,
                tests_completed INTEGER DEFAULT 0,
                correct_answers INTEGER DEFAULT 0,
                total_answers INTEGER DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users (user_id),
                UNIQUE(user_id, date)
            )
        """)

        await db.commit()


async def get_or_create_user(user_id: int, username: str = None, first_name: str = None):
    """Get existing user or create new one."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            "SELECT * FROM users WHERE user_id = ?", (user_id,)
        )
        user = await cursor.fetchone()

        if not user:
            await db.execute(
                "INSERT INTO users (user_id, username, first_name) VALUES (?, ?, ?)",
                (user_id, username, first_name)
            )
            await db.commit()
            cursor = await db.execute(
                "SELECT * FROM users WHERE user_id = ?", (user_id,)
            )
            user = await cursor.fetchone()

        return user


async def update_word_progress(user_id: int, word_id: str, is_correct: bool):
    """Update user's progress for a specific word."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            "SELECT * FROM progress WHERE user_id = ? AND word_id = ?",
            (user_id, word_id)
        )
        existing = await cursor.fetchone()

        now = datetime.now().isoformat()

        if existing:
            if is_correct:
                await db.execute(
                    """UPDATE progress
                       SET correct_count = correct_count + 1, last_reviewed = ?
                       WHERE user_id = ? AND word_id = ?""",
                    (now, user_id, word_id)
                )
            else:
                await db.execute(
                    """UPDATE progress
                       SET wrong_count = wrong_count + 1, last_reviewed = ?
                       WHERE user_id = ? AND word_id = ?""",
                    (now, user_id, word_id)
                )
        else:
            correct = 1 if is_correct else 0
            wrong = 0 if is_correct else 1
            await db.execute(
                """INSERT INTO progress (user_id, word_id, correct_count, wrong_count, last_reviewed)
                   VALUES (?, ?, ?, ?, ?)""",
                (user_id, word_id, correct, wrong, now)
            )

        await db.commit()


async def get_user_stats(user_id: int) -> dict:
    """Get user's learning statistics."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        # Total words stats
        cursor = await db.execute(
            """SELECT
                   COUNT(*) as total_words,
                   SUM(correct_count) as total_correct,
                   SUM(wrong_count) as total_wrong
               FROM progress WHERE user_id = ?""",
            (user_id,)
        )
        word_stats = await cursor.fetchone()

        # Grammar tests stats
        cursor = await db.execute(
            """SELECT
                   COUNT(*) as tests_count,
                   SUM(score) as total_score,
                   SUM(total) as total_questions
               FROM grammar_results WHERE user_id = ?""",
            (user_id,)
        )
        grammar_stats = await cursor.fetchone()

        # Mastered words (correct >= 3, no wrong in last 3)
        cursor = await db.execute(
            """SELECT COUNT(*) FROM progress
               WHERE user_id = ? AND correct_count >= 3 AND wrong_count = 0""",
            (user_id,)
        )
        mastered = await cursor.fetchone()

        return {
            "total_words": word_stats[0] or 0,
            "total_correct": word_stats[1] or 0,
            "total_wrong": word_stats[2] or 0,
            "tests_completed": grammar_stats[0] or 0,
            "grammar_score": grammar_stats[1] or 0,
            "grammar_total": grammar_stats[2] or 0,
            "mastered_words": mastered[0] or 0
        }


async def save_grammar_result(user_id: int, test_id: str, score: int, total: int):
    """Save grammar test result."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "INSERT INTO grammar_results (user_id, test_id, score, total) VALUES (?, ?, ?, ?)",
            (user_id, test_id, score, total)
        )
        await db.commit()


async def update_daily_stats(user_id: int, words: int = 0, tests: int = 0, correct: int = 0, total: int = 0):
    """Update daily statistics for user."""
    today = datetime.now().strftime("%Y-%m-%d")

    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            "SELECT * FROM daily_stats WHERE user_id = ? AND date = ?",
            (user_id, today)
        )
        existing = await cursor.fetchone()

        if existing:
            await db.execute(
                """UPDATE daily_stats
                   SET words_learned = words_learned + ?,
                       tests_completed = tests_completed + ?,
                       correct_answers = correct_answers + ?,
                       total_answers = total_answers + ?
                   WHERE user_id = ? AND date = ?""",
                (words, tests, correct, total, user_id, today)
            )
        else:
            await db.execute(
                """INSERT INTO daily_stats (user_id, date, words_learned, tests_completed, correct_answers, total_answers)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (user_id, today, words, tests, correct, total)
            )

        await db.commit()


async def get_users_for_reminder(hour: int, minute: int) -> list:
    """Get users who should receive reminder at given time."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            """SELECT user_id FROM users
               WHERE reminder_enabled = 1 AND reminder_hour = ? AND reminder_minute = ?""",
            (hour, minute)
        )
        users = await cursor.fetchall()
        return [u[0] for u in users]


async def set_reminder(user_id: int, enabled: bool, hour: int = 9, minute: int = 0):
    """Set reminder settings for user."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "UPDATE users SET reminder_enabled = ?, reminder_hour = ?, reminder_minute = ? WHERE user_id = ?",
            (1 if enabled else 0, hour, minute, user_id)
        )
        await db.commit()
