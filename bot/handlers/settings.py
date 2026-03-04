"""
Settings menu — уровень, напоминания, отзыв, сброс прогресса.

Все callback_data начинаются с "set_" и обрабатываются одним
standalone CallbackQueryHandler (без ConversationHandler).
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from bot.database import (
    get_user_settings, set_user_level, set_reminder,
    reset_user_progress, get_feedback_count
)
from bot.content_manager import get_levels_with_content

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def _reminder_status_text(settings: dict) -> str:
    """Human-readable reminder status."""
    if settings.get("reminder_enabled"):
        h = settings.get("reminder_hour", 9)
        m = settings.get("reminder_minute", 0)
        return f"Включены ({h:02d}:{m:02d} UTC)"
    return "Выключены"


# ──────────────────────────────────────────────
# Main settings menu
# ──────────────────────────────────────────────

async def _show_menu(query, context, user_id: int):
    """Render the main settings screen."""
    settings = await get_user_settings(user_id)
    fb_count = await get_feedback_count(user_id)

    level_str = f"{settings['major_level']}.{settings['sub_level']}"
    reminder_str = _reminder_status_text(settings)
    fb_str = f"{fb_count} отправлено" if fb_count else "нет"

    text = (
        "⚙️ Настройки\n"
        f"{'━' * 30}\n\n"
        f"📊 Уровень: {level_str}\n"
        f"⏰ Напоминания: {reminder_str}\n"
        f"💬 Отзывы: {fb_str}\n"
    )

    keyboard = [
        [InlineKeyboardButton("📊 Изменить уровень", callback_data="set_level")],
        [InlineKeyboardButton("⏰ Напоминания", callback_data="set_remind")],
        [InlineKeyboardButton("💬 Отзыв", callback_data="feedback_show")],
        [InlineKeyboardButton("🗑 Сброс прогресса", callback_data="set_reset")],
    ]

    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))


# ──────────────────────────────────────────────
# Level selection
# ──────────────────────────────────────────────

async def _show_level_selection(query, context, user_id: int):
    """Show level picker."""
    settings = await get_user_settings(user_id)
    current_major = settings["major_level"]
    current_sub = settings["sub_level"]

    levels = get_levels_with_content()
    if not levels:
        await query.edit_message_text("Нет доступных уровней с контентом.")
        return

    keyboard = []
    for lvl in levels:
        is_current = lvl["major"] == current_major and lvl["sub"] == current_sub
        label = f"{'✓ ' if is_current else ''}{lvl['display_name']}"
        keyboard.append([
            InlineKeyboardButton(label, callback_data=f"set_lvl_{lvl['major']}_{lvl['sub']}")
        ])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="set_menu")])

    await query.edit_message_text(
        f"📊 Текущий уровень: {current_major}.{current_sub}\n\n"
        "Выберите новый уровень:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def _handle_level_choice(query, context, user_id: int, data: str):
    """Save chosen level."""
    # data = "set_lvl_A1_1"
    parts = data.replace("set_lvl_", "").split("_")
    if len(parts) != 2:
        return await _show_menu(query, context, user_id)

    major, sub = parts
    await set_user_level(user_id, major, sub)
    context.user_data["user_level"] = (major, sub)

    await query.edit_message_text(
        f"✅ Уровень изменён на {major}.{sub}",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Назад к настройкам", callback_data="set_menu")]
        ])
    )


# ──────────────────────────────────────────────
# Reminders
# ──────────────────────────────────────────────

async def _show_reminder_settings(query, context, user_id: int):
    """Show reminder sub-menu."""
    settings = await get_user_settings(user_id)
    status_str = _reminder_status_text(settings)

    keyboard = [
        [InlineKeyboardButton("🔔 9:00", callback_data="set_rem_on_9"),
         InlineKeyboardButton("🔔 12:00", callback_data="set_rem_on_12")],
        [InlineKeyboardButton("🔔 18:00", callback_data="set_rem_on_18"),
         InlineKeyboardButton("🔔 21:00", callback_data="set_rem_on_21")],
        [InlineKeyboardButton("🔕 Выключить", callback_data="set_rem_off")],
        [InlineKeyboardButton("🔙 Назад", callback_data="set_menu")],
    ]

    await query.edit_message_text(
        f"⏰ Напоминания\n\n"
        f"Текущий статус: {status_str}\n\n"
        "Выберите время ежедневного напоминания (UTC).\n"
        "Москва = UTC+3.",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def _handle_reminder_choice(query, context, user_id: int, data: str):
    """Toggle or set reminder time."""
    if data == "set_rem_off":
        await set_reminder(user_id, enabled=False)
        result = "🔕 Напоминания выключены."
    else:
        # data = "set_rem_on_9"
        hour = int(data.replace("set_rem_on_", ""))
        await set_reminder(user_id, enabled=True, hour=hour, minute=0)
        result = f"🔔 Напоминания включены: {hour:02d}:00 UTC"

    await query.edit_message_text(
        result,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Назад к настройкам", callback_data="set_menu")]
        ])
    )


# ──────────────────────────────────────────────
# Reset progress
# ──────────────────────────────────────────────

async def _show_reset_confirm(query, context, user_id: int):
    """Show reset confirmation warning."""
    await query.edit_message_text(
        "🗑 Сброс прогресса\n\n"
        "⚠️ Это действие удалит ВСЕ ваши данные:\n"
        "• Прогресс по словам и фразам\n"
        "• Результаты грамматических тестов\n"
        "• Дневную статистику\n"
        "• Прогресс по диалогам, культуре, упражнениям\n\n"
        "Отменить сброс будет невозможно!",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Да, сбросить всё", callback_data="set_reset_yes")],
            [InlineKeyboardButton("🔙 Отмена", callback_data="set_menu")],
        ])
    )


async def _handle_reset(query, context, user_id: int):
    """Execute progress reset."""
    try:
        await reset_user_progress(user_id)
        await query.edit_message_text(
            "✅ Прогресс полностью сброшен.\n\n"
            "Вы можете начать изучение заново!",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Назад к настройкам", callback_data="set_menu")]
            ])
        )
        logger.info(f"User {user_id} reset all progress")
    except Exception as e:
        logger.error(f"Error resetting progress for user {user_id}: {e}", exc_info=True)
        await query.edit_message_text(
            "❌ Ошибка при сбросе прогресса. Попробуйте позже.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Назад к настройкам", callback_data="set_menu")]
            ])
        )


# ──────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────

async def show_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /settings command — send a new message with settings menu."""
    user_id = update.effective_user.id
    settings = await get_user_settings(user_id)
    fb_count = await get_feedback_count(user_id)

    level_str = f"{settings['major_level']}.{settings['sub_level']}"
    reminder_str = _reminder_status_text(settings)
    fb_str = f"{fb_count} отправлено" if fb_count else "нет"

    text = (
        "⚙️ Настройки\n"
        f"{'━' * 30}\n\n"
        f"📊 Уровень: {level_str}\n"
        f"⏰ Напоминания: {reminder_str}\n"
        f"💬 Отзывы: {fb_str}\n"
    )

    keyboard = [
        [InlineKeyboardButton("📊 Изменить уровень", callback_data="set_level")],
        [InlineKeyboardButton("⏰ Напоминания", callback_data="set_remind")],
        [InlineKeyboardButton("💬 Отзыв", callback_data="feedback_show")],
        [InlineKeyboardButton("🗑 Сброс прогресса", callback_data="set_reset")],
    ]

    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))


async def settings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Route all set_* callbacks."""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    data = query.data

    try:
        if data == "set_menu" or data == "set_back":
            await _show_menu(query, context, user_id)

        elif data == "set_level":
            await _show_level_selection(query, context, user_id)

        elif data.startswith("set_lvl_"):
            await _handle_level_choice(query, context, user_id, data)

        elif data == "set_remind":
            await _show_reminder_settings(query, context, user_id)

        elif data.startswith("set_rem_"):
            await _handle_reminder_choice(query, context, user_id, data)

        elif data == "set_reset":
            await _show_reset_confirm(query, context, user_id)

        elif data == "set_reset_yes":
            await _handle_reset(query, context, user_id)

        else:
            logger.warning(f"Unknown settings callback: {data}")
            await _show_menu(query, context, user_id)

    except Exception as e:
        logger.error(f"Error in settings_callback ({data}): {e}", exc_info=True)
        try:
            await query.edit_message_text(
                f"❌ Произошла ошибка: {e}",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Назад к настройкам", callback_data="set_menu")]
                ])
            )
        except Exception:
            pass
