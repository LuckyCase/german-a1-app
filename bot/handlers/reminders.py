import random
from datetime import datetime, timezone
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ContextTypes

from bot.database import get_users_for_reminder
from bot.content_manager import get_all_words
from bot.config import WEB_APP_URL

# Motivational messages
REMINDER_MESSAGES = [
    "Zeit für Deutsch! Время учить немецкий! 🇩🇪",
    "Guten Tag! Не забудь попрактиковаться сегодня! 📚",
    "Ein Wort am Tag - und du wirst Meister! Одно слово в день - и ты станешь мастером! 💪",
    "Dein Deutsch wartet auf dich! Твой немецкий ждёт тебя! ⏰",
    "Übung macht den Meister! Практика делает мастера! 🎯",
    "Los geht's! Пора учиться! 🚀",
    "Heute ist ein guter Tag zum Lernen! Сегодня хороший день для учёбы! ☀️",
]


async def send_reminder(context: ContextTypes.DEFAULT_TYPE):
    """Job function to send reminders."""
    now = datetime.now(timezone.utc)
    hour = now.hour
    minute = now.minute

    # Get users who should receive reminder at this time
    users = await get_users_for_reminder(hour, minute)

    for user_id in users:
        try:
            # Get a random word to include in the reminder
            words = get_all_words()
            word = random.choice(words)

            message = random.choice(REMINDER_MESSAGES)

            text = (
                f"{message}\n\n"
                f"📖 Слово дня:\n"
                f"**{word['de']}** - {word['ru']}\n"
                f"_{word.get('example', '')}_\n\n"
                f"Продолжите занятия в приложении."
            )

            reply_markup = None
            if WEB_APP_URL:
                reply_markup = InlineKeyboardMarkup(
                    [[InlineKeyboardButton("🚀 Открыть приложение", web_app=WebAppInfo(url=WEB_APP_URL))]]
                )

            await context.bot.send_message(
                chat_id=user_id,
                text=text,
                parse_mode="Markdown",
                reply_markup=reply_markup,
            )
        except Exception as e:
            # User might have blocked the bot
            print(f"Could not send reminder to {user_id}: {e}")


def setup_reminder_job(application):
    """Set up the reminder job to run every minute."""
    job_queue = application.job_queue

    # Run every minute to check for reminders
    job_queue.run_repeating(
        send_reminder,
        interval=60,  # Check every minute
        first=10  # Start after 10 seconds
    )
