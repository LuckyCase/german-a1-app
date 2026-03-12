"""Diagnostic placement test handler for new users."""
import random
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, ConversationHandler, CallbackQueryHandler
)

from bot.content_manager import get_diagnostic_questions
from bot.database import set_user_level, get_pool

logger = logging.getLogger(__name__)

# Conversation states (unique range: 40-42)
DIAG_QUESTION, DIAG_RESULT = range(40, 42)


async def _mark_diagnostic_completed(user_id: int):
    """Mark user's diagnostic as completed."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE users SET diagnostic_completed = 1 WHERE user_id = $1",
            user_id
        )


async def diagnostic_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """User accepted diagnostic test. Load questions and start."""
    query = update.callback_query
    await query.answer()

    questions = get_diagnostic_questions()
    if not questions:
        await query.edit_message_text("Тест недоступен. Выберите уровень вручную в /settings.")
        await _mark_diagnostic_completed(update.effective_user.id)
        return ConversationHandler.END

    random.shuffle(questions)

    context.user_data["diag_questions"] = questions
    context.user_data["diag_index"] = 0
    context.user_data["diag_correct"] = 0

    await query.edit_message_text(
        "Диагностический тест\n\n"
        "15 вопросов для определения вашего уровня.\n"
        "Не переживайте, если не знаете ответ — просто угадайте!\n",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Начать!", callback_data="diag_next")]
        ])
    )
    return DIAG_QUESTION


async def show_diagnostic_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show next diagnostic question."""
    query = update.callback_query
    await query.answer()

    questions = context.user_data.get("diag_questions", [])
    index = context.user_data.get("diag_index", 0)

    if index >= len(questions):
        return await _show_diagnostic_result(query, context)

    q = questions[index]
    options = q.get("options", [])

    keyboard = []
    for i, opt in enumerate(options):
        keyboard.append([InlineKeyboardButton(opt, callback_data=f"diag_ans_{i}")])

    await query.edit_message_text(
        f"Вопрос {index + 1} из {len(questions)}\n\n"
        f"{q.get('question', '')}",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return DIAG_QUESTION


async def handle_diagnostic_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle diagnostic answer — no feedback, just count."""
    query = update.callback_query
    await query.answer()

    questions = context.user_data.get("diag_questions", [])
    index = context.user_data.get("diag_index", 0)

    if index < len(questions):
        answer_index = int(query.data.replace("diag_ans_", ""))
        correct_index = questions[index].get("correct", 0)
        if answer_index == correct_index:
            context.user_data["diag_correct"] = context.user_data.get("diag_correct", 0) + 1

    context.user_data["diag_index"] = index + 1

    # Show next question immediately (no feedback in diagnostic)
    if context.user_data["diag_index"] >= len(questions):
        return await _show_diagnostic_result(query, context)

    return await show_diagnostic_question(update, context)


async def _show_diagnostic_result(query, context):
    """Show diagnostic result with recommended level."""
    correct = context.user_data.get("diag_correct", 0)
    total = len(context.user_data.get("diag_questions", []))

    if correct <= 5:
        recommended_level = ("A1", "1")
        level_name = "A1.1 (Начинающий)"
    elif correct <= 10:
        recommended_level = ("A1", "2")
        level_name = "A1.2 (Продолжающий A1)"
    else:
        # A2 content not fully available yet
        recommended_level = ("A1", "2")
        level_name = "A1.2 (Контент A2 в разработке)"

    context.user_data["diag_recommended"] = recommended_level
    context.user_data["diag_level_name"] = level_name

    await query.edit_message_text(
        f"Результат: {correct} из {total}\n\n"
        f"Рекомендуемый уровень: {level_name}\n\n"
        f"Принять рекомендацию или выбрать уровень вручную?",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(f"Принять ({level_name})", callback_data="diag_accept")],
            [InlineKeyboardButton("Выбрать вручную", callback_data="diag_manual")]
        ])
    )
    return DIAG_RESULT


async def diagnostic_accept(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Accept recommended level."""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    major, sub = context.user_data.get("diag_recommended", ("A1", "1"))

    await set_user_level(user_id, major, sub)
    context.user_data["user_level"] = (major, sub)
    await _mark_diagnostic_completed(user_id)

    await query.edit_message_text(
        f"Уровень установлен: {major}.{sub}\n\n"
        f"Используйте /start чтобы начать обучение!"
    )
    return ConversationHandler.END


async def diagnostic_manual(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show manual level selection."""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    await _mark_diagnostic_completed(user_id)

    from bot.content_manager import get_levels_with_content
    levels = get_levels_with_content()

    keyboard = []
    for level in levels:
        keyboard.append([InlineKeyboardButton(
            level["display_name"],
            callback_data=f"diag_set_{level['major']}_{level['sub']}"
        )])

    await query.edit_message_text(
        "Выберите уровень:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return DIAG_RESULT


async def diagnostic_set_level(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set manually selected level."""
    query = update.callback_query
    await query.answer()

    parts = query.data.replace("diag_set_", "").split("_")
    if len(parts) == 2:
        major, sub = parts
        user_id = update.effective_user.id
        await set_user_level(user_id, major, sub)
        context.user_data["user_level"] = (major, sub)

        await query.edit_message_text(
            f"Уровень установлен: {major}.{sub}\n\n"
            f"Используйте /start чтобы начать обучение!"
        )
    else:
        await query.edit_message_text("Ошибка. Используйте /settings для выбора уровня.")

    return ConversationHandler.END


async def diagnostic_skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """User skipped diagnostic — go to manual level selection."""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    await _mark_diagnostic_completed(user_id)

    from bot.content_manager import get_levels_with_content
    levels = get_levels_with_content()

    keyboard = []
    for level in levels:
        keyboard.append([InlineKeyboardButton(
            level["display_name"],
            callback_data=f"diag_set_{level['major']}_{level['sub']}"
        )])

    await query.edit_message_text(
        "Выберите ваш уровень немецкого:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return DIAG_RESULT


def get_diagnostic_handler():
    """Build ConversationHandler for diagnostic test."""
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(diagnostic_start, pattern="^diag_start$"),
            CallbackQueryHandler(diagnostic_skip, pattern="^diag_skip$"),
        ],
        states={
            DIAG_QUESTION: [
                CallbackQueryHandler(show_diagnostic_question, pattern="^diag_next$"),
                CallbackQueryHandler(handle_diagnostic_answer, pattern="^diag_ans_"),
            ],
            DIAG_RESULT: [
                CallbackQueryHandler(diagnostic_accept, pattern="^diag_accept$"),
                CallbackQueryHandler(diagnostic_manual, pattern="^diag_manual$"),
                CallbackQueryHandler(diagnostic_set_level, pattern="^diag_set_"),
            ],
        },
        fallbacks=[],
        per_message=False,
        per_chat=True,
        per_user=True,
    )
