from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ContextTypes
import logging

from bot.database import get_or_create_user, get_user_settings, get_user_streak
from bot.config import WEB_APP_URL, DATABASE_URL

logger = logging.getLogger(__name__)


async def redirect_commands_to_webapp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Любая команда в чате кроме обработанных выше — напоминание открыть Web App."""
    await update.message.reply_text(
        "Все занятия и настройки доступны только в приложении.\n\n"
        "Нажмите /start и откройте «🚀 Открыть приложение»."
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Единственное пользовательское сообщение из чата: приветствие и кнопка Web App."""
    user = update.effective_user

    diagnostic_completed = True
    if DATABASE_URL:
        try:
            await get_or_create_user(user.id, user.username, user.first_name)
            settings = await get_user_settings(user.id)
            context.user_data["user_level"] = (
                settings.get("major_level", "A1"),
                settings.get("sub_level", "1"),
            )
            diagnostic_completed = bool(settings.get("diagnostic_completed", 1))
        except Exception as e:
            logger.error(f"Failed to register user: {e}")

    streak = 0
    if DATABASE_URL:
        try:
            streak = await get_user_streak(user.id)
        except Exception:
            pass

    streak_text = (
        f"\n🔥 Серия: {streak} {'день' if streak == 1 else 'дней'} подряд!\n"
        if streak > 0
        else ""
    )

    diagnostic_hint = ""
    if not diagnostic_completed:
        diagnostic_hint = (
            "\n\nℹ️ Тест на определение уровня и выбор уровня — внутри приложения."
        )

    if not WEB_APP_URL:
        await update.message.reply_text(
            "Приложение сейчас недоступно (не настроен адрес Web App). "
            "Попробуйте позже или напишите администратору."
        )
        return

    message = (
        f"Hallo, {user.first_name}! 👋\n\n"
        f"🇩🇪 German A1 — учите немецкий в удобном приложении.\n"
        f"{streak_text}\n"
        f"Слова, грамматика, фразы, диалоги, прогресс и напоминания — "
        f"всё в одном месте. Откройте его кнопкой ниже."
        f"{diagnostic_hint}"
    )

    keyboard = [
        [InlineKeyboardButton("🚀 Открыть приложение", web_app=WebAppInfo(url=WEB_APP_URL))]
    ]

    await update.message.reply_text(
        message,
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
