import random
from datetime import time, datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from bot.database import set_reminder, get_users_for_reminder, get_or_create_user
from bot.data.vocabulary import get_all_words

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


async def reminder_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show reminder settings."""
    keyboard = [
        [InlineKeyboardButton("🔔 Включить (9:00)", callback_data="rem_on_9")],
        [InlineKeyboardButton("🔔 Включить (12:00)", callback_data="rem_on_12")],
        [InlineKeyboardButton("🔔 Включить (18:00)", callback_data="rem_on_18")],
        [InlineKeyboardButton("🔔 Включить (21:00)", callback_data="rem_on_21")],
        [InlineKeyboardButton("🔕 Выключить напоминания", callback_data="rem_off")],
    ]

    await update.message.reply_text(
        "⏰ Настройка ежедневных напоминаний\n\n"
        "Выберите время, когда бот будет напоминать вам об изучении немецкого.\n"
        "Время указано в UTC (Москва = UTC+3).",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def reminder_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle reminder settings callbacks."""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id

    if query.data == "rem_off":
        await set_reminder(user_id, enabled=False)
        await query.edit_message_text(
            "🔕 Напоминания выключены.\n\n"
            "Вы можете включить их снова командой /reminder"
        )
    else:
        # Parse time from callback data
        hour = int(query.data.replace("rem_on_", ""))
        await set_reminder(user_id, enabled=True, hour=hour, minute=0)
        await query.edit_message_text(
            f"🔔 Напоминания включены!\n\n"
            f"Время: {hour}:00 UTC\n"
            f"Вы будете получать ежедневные напоминания об изучении немецкого.\n\n"
            f"Изменить настройки: /reminder"
        )


async def send_reminder(context: ContextTypes.DEFAULT_TYPE):
    """Job function to send reminders."""
    now = datetime.utcnow()
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
                f"Команды:\n"
                f"/flashcards - учить слова\n"
                f"/grammar - грамматика\n"
                f"/progress - ваш прогресс"
            )

            keyboard = [
                [InlineKeyboardButton("📚 Начать учиться", callback_data="start_flashcards")]
            ]

            await context.bot.send_message(
                chat_id=user_id,
                text=text,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
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
