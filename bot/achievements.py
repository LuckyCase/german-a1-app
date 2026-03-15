"""Achievement definitions and checking logic."""
import json
import logging

logger = logging.getLogger(__name__)

ACHIEVEMENTS = [
    {
        "id": "first_steps",
        "emoji": "\U0001f331",  # 🌱
        "name": "Первые шаги",
        "description": "Изучите 10 слов",
    },
    {
        "id": "week_streak",
        "emoji": "\U0001f525",  # 🔥
        "name": "Неделя подряд",
        "description": "7-дневная серия занятий",
    },
    {
        "id": "grammarian",
        "emoji": "\U0001f4da",  # 📚
        "name": "Грамматик",
        "description": "Пройдите все грамматические тесты A1",
    },
    {
        "id": "chatterbox",
        "emoji": "\U0001f4ac",  # 💬
        "name": "Болтун",
        "description": "Изучите 50 фраз",
    },
    {
        "id": "master_a1",
        "emoji": "\U0001f3c6",  # 🏆
        "name": "Мастер A1",
        "description": "80% прогресса по всем разделам A1",
    },
]

ACHIEVEMENT_MAP = {a["id"]: a for a in ACHIEVEMENTS}


async def check_achievements(user_id: int, current_streak: int) -> list:
    """Check and unlock any new achievements. Returns list of newly unlocked achievement dicts."""
    from bot.database import get_pool, get_user_achievements

    existing = await get_user_achievements(user_id)
    existing_ids = set(existing)
    newly_unlocked = []

    logger.info(f"Checking achievements for user {user_id}, streak={current_streak}, existing={existing_ids}")

    pool = await get_pool()
    async with pool.acquire() as conn:
        # Check each achievement
        for ach in ACHIEVEMENTS:
            if ach["id"] in existing_ids:
                continue

            unlocked = False

            if ach["id"] == "first_steps":
                row = await conn.fetchrow(
                    "SELECT COUNT(*) as c FROM progress WHERE user_id = $1",
                    user_id
                )
                count = row["c"] or 0
                unlocked = count >= 10
                logger.info(f"  first_steps: words={count}/10, unlocked={unlocked}")

            elif ach["id"] == "week_streak":
                unlocked = current_streak >= 7
                logger.info(f"  week_streak: streak={current_streak}/7, unlocked={unlocked}")

            elif ach["id"] == "grammarian":
                row = await conn.fetchrow(
                    "SELECT COUNT(DISTINCT test_id) as c FROM grammar_results WHERE user_id = $1",
                    user_id
                )
                count = row["c"] or 0
                unlocked = count >= 16
                logger.info(f"  grammarian: tests={count}/16, unlocked={unlocked}")

            elif ach["id"] == "chatterbox":
                row = await conn.fetchrow(
                    "SELECT COUNT(*) as c FROM phrases_progress WHERE user_id = $1",
                    user_id
                )
                count = row["c"] or 0
                unlocked = count >= 50
                logger.info(f"  chatterbox: phrases={count}/50, unlocked={unlocked}")

            elif ach["id"] == "master_a1":
                from bot.content_manager import get_all_words
                total_a1 = len(get_all_words("A1", "1")) + len(get_all_words("A1", "2"))
                if total_a1 > 0:
                    mastered = await conn.fetchrow(
                        """SELECT COUNT(*) as c FROM progress
                           WHERE user_id = $1 AND correct_count >= 3 AND wrong_count = 0""",
                        user_id
                    )
                    mastered_count = mastered["c"] or 0
                    unlocked = (mastered_count / total_a1) >= 0.8
                    logger.info(f"  master_a1: mastered={mastered_count}/{total_a1}, unlocked={unlocked}")

            if unlocked:
                newly_unlocked.append(ach)

        # Save newly unlocked achievements
        if newly_unlocked:
            new_ids = existing + [a["id"] for a in newly_unlocked]
            await conn.execute(
                "UPDATE users SET achievements = $1 WHERE user_id = $2",
                json.dumps(new_ids), user_id
            )
            logger.info(f"  UNLOCKED: {[a['id'] for a in newly_unlocked]}, saved: {new_ids}")
        else:
            logger.info(f"  No new achievements unlocked")

    return newly_unlocked


def get_achievement_display(achievement_ids: list) -> str:
    """Format achievements for display."""
    if not achievement_ids:
        return ""
    lines = []
    for aid in achievement_ids:
        ach = ACHIEVEMENT_MAP.get(aid)
        if ach:
            lines.append(f"   {ach['emoji']} {ach['name']}")
    return "\n".join(lines)
