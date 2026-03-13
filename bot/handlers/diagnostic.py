"""Diagnostic placement test handler for new users."""
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, ConversationHandler, CallbackQueryHandler
)

from bot.content_manager import (
    get_diagnostic_test,
    get_diagnostic_questions,
    get_diagnostic_stages,
    recommend_diagnostic_level,
)
from bot.database import set_user_level, get_pool

logger = logging.getLogger(__name__)

# Conversation states (unique range: 40-43)
DIAG_QUESTION, DIAG_DECISION, DIAG_RESULT = range(40, 43)


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

    test_data = get_diagnostic_test()
    stages = get_diagnostic_stages()
    if not stages:
        await query.edit_message_text("Тест недоступен. Выберите уровень вручную в /settings.")
        await _mark_diagnostic_completed(update.effective_user.id)
        return ConversationHandler.END

    context.user_data["diag_test_data"] = test_data
    context.user_data["diag_stages"] = stages
    context.user_data["diag_stage_index"] = 0
    context.user_data["diag_stage_results"] = {}
    _prepare_current_stage(context)

    await query.edit_message_text(
        "Диагностический тест\n\n"
        "Многоэтапная проверка уровня:\n"
        "1) A1-A2\n"
        "2) B1-B2 (предложим при хорошем результате)\n"
        "3) C1-C2 (предложим при хорошем результате)\n\n"
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
    stage = _get_current_stage(context)

    if index >= len(questions):
        return await _show_stage_outcome(query, context)

    q = questions[index]
    options = q.get("options", [])

    keyboard = []
    for i, opt in enumerate(options):
        keyboard.append([InlineKeyboardButton(opt, callback_data=f"diag_ans_{i}")])

    await query.edit_message_text(
        f"{stage.get('name', 'Диагностика')}\n"
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
        return await _show_stage_outcome(query, context)

    return await show_diagnostic_question(update, context)


def _get_current_stage(context: ContextTypes.DEFAULT_TYPE) -> dict:
    """Get currently active stage metadata."""
    stages = context.user_data.get("diag_stages", [])
    stage_index = context.user_data.get("diag_stage_index", 0)
    if 0 <= stage_index < len(stages):
        return stages[stage_index]
    return {}


def _prepare_current_stage(context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Prepare questions for current stage."""
    stage = _get_current_stage(context)
    stage_id = stage.get("id")
    if not stage_id:
        return False

    questions_limit = stage.get("questions_count")
    questions = get_diagnostic_questions(
        stage_id=stage_id,
        limit=questions_limit,
        shuffle=True,
    )
    if not questions:
        return False

    context.user_data["diag_questions"] = questions
    context.user_data["diag_index"] = 0
    context.user_data["diag_correct"] = 0
    context.user_data["diag_current_stage_id"] = stage_id
    return True


async def _show_stage_outcome(query, context):
    """Store stage result and either offer next stage or show final result."""
    stage = _get_current_stage(context)
    stage_id = stage.get("id")
    correct = context.user_data.get("diag_correct", 0)
    total = len(context.user_data.get("diag_questions", []))
    ratio = (correct / total) if total else 0

    stage_results = context.user_data.get("diag_stage_results", {})
    stage_results[stage_id] = {
        "correct": correct,
        "total": total
    }
    context.user_data["diag_stage_results"] = stage_results

    stages = context.user_data.get("diag_stages", [])
    has_next = context.user_data.get("diag_stage_index", 0) + 1 < len(stages)
    pass_threshold = float(stage.get("offer_next_if_score_at_least", 1.1))

    if has_next and ratio >= pass_threshold:
        next_stage_name = stages[context.user_data["diag_stage_index"] + 1].get("name", "следующий этап")
        await query.edit_message_text(
            f"Этап завершен: {stage.get('name', 'Диагностика')}\n"
            f"Результат: {correct} из {total}\n\n"
            f"Хотите продолжить и пройти {next_stage_name}?",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Продолжить", callback_data="diag_continue_stage")],
                [InlineKeyboardButton("Завершить и получить результат", callback_data="diag_finish_now")]
            ])
        )
        return DIAG_DECISION

    return await _show_diagnostic_result(query, context)


async def diagnostic_continue_stage(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Continue to the next diagnostic stage."""
    query = update.callback_query
    await query.answer()

    context.user_data["diag_stage_index"] = context.user_data.get("diag_stage_index", 0) + 1
    if not _prepare_current_stage(context):
        return await _show_diagnostic_result(query, context)
    return await show_diagnostic_question(update, context)


async def diagnostic_finish_now(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Finish diagnostic and show final recommendation."""
    query = update.callback_query
    await query.answer()
    return await _show_diagnostic_result(query, context)


async def _show_diagnostic_result(query, context):
    """Show final diagnostic result with recommended level."""
    stage_results = context.user_data.get("diag_stage_results", {})
    recommendation = recommend_diagnostic_level(stage_results)

    recommended_level = (recommendation.get("major", "A1"), recommendation.get("sub", "1"))
    level_name = recommendation.get("name", "A1.1 (Начинающий)")

    completed_lines = []
    stage_labels = {
        "A1_A2": "A1-A2",
        "B1_B2": "B1-B2",
        "C1_C2": "C1-C2",
    }
    for stage_id, stats in stage_results.items():
        completed_lines.append(
            f"• {stage_labels.get(stage_id, stage_id)}: {stats.get('correct', 0)}/{stats.get('total', 0)}"
        )
    completed_block = "\n".join(completed_lines) if completed_lines else "• Нет данных"

    if recommended_level[0] in {"B1", "B2", "C1", "C2"}:
        level_hint = "\n\nПримечание: контент продвинутых уровней в приложении может быть ограничен."
    else:
        level_hint = ""

    context.user_data["diag_recommended"] = recommended_level
    context.user_data["diag_level_name"] = level_name

    await query.edit_message_text(
        f"Результаты по этапам:\n{completed_block}\n\n"
        f"Рекомендуемый уровень: {level_name}\n\n"
        f"Принять рекомендацию или выбрать уровень вручную?{level_hint}",
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

    from bot.content_manager import get_available_levels
    levels = get_available_levels()

    keyboard = []
    for level in levels:
        label = level["display_name"]
        if not level.get("has_content", False):
            label = f"{label} (в разработке)"
        keyboard.append([InlineKeyboardButton(
            label,
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

    from bot.content_manager import get_available_levels
    levels = get_available_levels()

    keyboard = []
    for level in levels:
        label = level["display_name"]
        if not level.get("has_content", False):
            label = f"{label} (в разработке)"
        keyboard.append([InlineKeyboardButton(
            label,
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
            DIAG_DECISION: [
                CallbackQueryHandler(diagnostic_continue_stage, pattern="^diag_continue_stage$"),
                CallbackQueryHandler(diagnostic_finish_now, pattern="^diag_finish_now$"),
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
