import random
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, CallbackQueryHandler

from bot.content_manager import (
    get_phrases_categories, get_phrases_by_category, get_all_phrases_flat,
    get_current_level, get_current_level_str, get_levels_with_content,
    get_phrases_by_ids
)
from bot.database import (
    save_phrase_progress, update_daily_stats,
    get_priority_phrase_ids, get_all_error_phrase_ids,
    get_due_phrase_ids, get_reviewed_phrase_ids, update_user_activity,
    check_and_notify_achievements
)

logger = logging.getLogger(__name__)

# Conversation states
PF_LEVEL_SELECT, PF_CATEGORY_SELECT, PF_LEARNING, PF_ANSWER = range(10, 14)

SESSION_SIZE = 10
MAX_ERROR_PHRASES = 5


def _get_pf_level(context) -> tuple:
    """Get level from user session, falling back to global current level."""
    return context.user_data.get("pf_level", get_current_level())


async def _build_session_phrases(user_id: int, phrases: list) -> list:
    """Build a session of up to SESSION_SIZE phrases using SRS priority.

    1. Phrases due for SRS review (next_review_at <= NOW)
    2. New phrases the user has never seen
    3. Random phrases if still not enough
    """
    if not phrases:
        return []

    # Track user activity for streak
    await update_user_activity(user_id)

    phrase_ids = [p["phrase_id"] for p in phrases]
    phrase_map = {p["phrase_id"]: p for p in phrases}

    # 1. SRS due phrases
    due_ids = await get_due_phrase_ids(user_id, phrase_ids, limit=SESSION_SIZE)
    session_ids = list(due_ids)

    # 2. New phrases (never reviewed)
    if len(session_ids) < SESSION_SIZE:
        reviewed = await get_reviewed_phrase_ids(user_id, phrase_ids)
        new_ids = [pid for pid in phrase_ids if pid not in reviewed]
        random.shuffle(new_ids)
        for pid in new_ids:
            if len(session_ids) >= SESSION_SIZE:
                break
            if pid not in session_ids:
                session_ids.append(pid)

    # 3. Fill with random
    if len(session_ids) < SESSION_SIZE:
        remaining = [pid for pid in phrase_ids if pid not in set(session_ids)]
        random.shuffle(remaining)
        session_ids.extend(remaining[:SESSION_SIZE - len(session_ids)])

    session = [phrase_map[pid] for pid in session_ids if pid in phrase_map]
    random.shuffle(session)
    return session


async def phrases_flashcards_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start phrases flashcards session."""
    try:
        context.user_data["pf_level"] = context.user_data.get("user_level", get_current_level())

        levels = get_levels_with_content()

        if len(levels) > 1:
            keyboard = []
            for level in levels:
                keyboard.append([
                    InlineKeyboardButton(
                        f"{'✓ ' if level['is_current'] else ''}{level['display_name']}",
                        callback_data=f"pf_level_{level['major']}_{level['sub']}"
                    )
                ])
            keyboard.append([InlineKeyboardButton("Отмена", callback_data="pf_cancel")])

            reply_markup = InlineKeyboardMarkup(keyboard)
            text = (
                f"Текущий уровень: {get_current_level_str()}\n\n"
                "Выберите уровень:"
            )

            if update.message:
                await update.message.reply_text(text, reply_markup=reply_markup)
            elif update.callback_query:
                await update.callback_query.answer()
                await update.callback_query.edit_message_text(text, reply_markup=reply_markup)
            return PF_LEVEL_SELECT
        else:
            return await pf_show_categories(update, context)

    except Exception as e:
        logger.error(f"Error in phrases_flashcards_start: {e}", exc_info=True)
        try:
            err = f"Произошла ошибка: {e}"
            if update.message:
                await update.message.reply_text(err)
            elif update.callback_query:
                await update.callback_query.answer()
                await update.callback_query.edit_message_text(err)
        except Exception:
            pass
        return ConversationHandler.END


async def pf_level_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle level selection."""
    query = update.callback_query
    await query.answer()

    if query.data == "pf_cancel":
        await query.edit_message_text("Отменено. Используйте /phrases чтобы начать снова.")
        return ConversationHandler.END

    parts = query.data.replace("pf_level_", "").split("_")
    if len(parts) == 2:
        major, sub = parts
        context.user_data["pf_level"] = (major, sub)

    return await pf_show_categories(update, context)


async def pf_show_categories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show phrase categories."""
    try:
        major, sub = _get_pf_level(context)
        level_str = f"{major}.{sub}"
        categories = get_phrases_categories(major, sub)

        if not categories:
            err = f"Категории фраз для уровня {level_str} не найдены."
            if update.message:
                await update.message.reply_text(err)
            elif update.callback_query:
                await update.callback_query.edit_message_text(err)
            return ConversationHandler.END

        keyboard = []
        for cat in categories:
            keyboard.append([
                InlineKeyboardButton(
                    f"{cat['name']} ({cat['count']} фраз)",
                    callback_data=f"pf_cat_{cat['id']}"
                )
            ])
        keyboard.append([InlineKeyboardButton("Все фразы (случайно)", callback_data="pf_cat_all")])
        keyboard.append([InlineKeyboardButton("Отмена", callback_data="pf_cancel")])

        text = f"Уровень: {level_str}\n\nВыберите категорию фраз:"

        if update.message:
            await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        elif update.callback_query:
            await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

        return PF_CATEGORY_SELECT

    except Exception as e:
        logger.error(f"Error in pf_show_categories: {e}", exc_info=True)
        try:
            err = f"Произошла ошибка: {e}"
            if update.message:
                await update.message.reply_text(err)
            elif update.callback_query:
                await update.callback_query.edit_message_text(err)
        except Exception:
            pass
        return ConversationHandler.END


async def pf_category_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle phrase category selection."""
    query = update.callback_query
    await query.answer()

    if query.data == "pf_cancel":
        await query.edit_message_text("Отменено. Используйте /phrases чтобы начать снова.")
        return ConversationHandler.END

    category_id = query.data.replace("pf_cat_", "")
    user_id = update.effective_user.id
    major, sub = _get_pf_level(context)

    if category_id == "all":
        phrases = get_all_phrases_flat(major, sub)
        context.user_data["pf_category_name"] = "Все фразы"
    else:
        phrases = get_phrases_by_category(category_id, major, sub)
        if phrases:
            context.user_data["pf_category_name"] = phrases[0].get("category_name", category_id)
        else:
            context.user_data["pf_category_name"] = category_id

    # Deduplicate phrases by phrase_id (category files may have duplicates)
    seen = set()
    unique_phrases = []
    for p in phrases:
        if p["phrase_id"] not in seen:
            seen.add(p["phrase_id"])
            unique_phrases.append(p)

    session = await _build_session_phrases(user_id, unique_phrases)

    context.user_data["pf_phrases"] = session
    context.user_data["pf_index"] = 0
    context.user_data["pf_correct"] = 0
    context.user_data["pf_wrong"] = 0
    context.user_data["pf_errors_mode"] = False

    level_str = f"{major}.{sub}"
    await query.edit_message_text(
        f"Уровень: {level_str}\n"
        f"Категория: {context.user_data['pf_category_name']}\n"
        f"Карточек в сессии: {len(session)}\n\n"
        f"Готовы?",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Начать!", callback_data="pf_next")]
        ])
    )
    return PF_LEARNING


async def pf_errors_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start phrase error-review mode."""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    error_ids = await get_all_error_phrase_ids(user_id)

    if not error_ids:
        await query.edit_message_text(
            "Отлично! Ошибок в фразах нет.\n\n"
            "Используйте /phrases для изучения новых фраз."
        )
        return ConversationHandler.END

    batch_ids = error_ids[:SESSION_SIZE]
    phrases = get_phrases_by_ids(batch_ids)

    if not phrases:
        await query.edit_message_text(
            "Не удалось загрузить фразы для повторения.\n"
            "Используйте /phrases для изучения."
        )
        return ConversationHandler.END

    context.user_data["pf_phrases"] = phrases
    context.user_data["pf_index"] = 0
    context.user_data["pf_correct"] = 0
    context.user_data["pf_wrong"] = 0
    context.user_data["pf_errors_mode"] = True
    context.user_data["pf_remaining_error_ids"] = error_ids[SESSION_SIZE:]

    await query.edit_message_text(
        f"Работа над ошибками (фразы)\n\n"
        f"Фраз для повторения: {len(error_ids)}\n"
        f"Карточек в этой серии: {len(phrases)}\n\n"
        f"Нажмите чтобы начать!",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Начать!", callback_data="pf_next")]
        ])
    )
    return PF_LEARNING


async def pf_show_next(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show the next phrase card."""
    query = update.callback_query
    await query.answer()

    phrases = context.user_data.get("pf_phrases", [])
    index = context.user_data.get("pf_index", 0)

    if index >= len(phrases):
        correct = context.user_data.get("pf_correct", 0)
        wrong = context.user_data.get("pf_wrong", 0)
        total = correct + wrong

        user_id = update.effective_user.id
        await update_daily_stats(user_id, correct=correct, total=total)

        percentage = (correct / total * 100) if total > 0 else 0
        errors_mode = context.user_data.get("pf_errors_mode", False)
        remaining_ids = context.user_data.get("pf_remaining_error_ids", [])

        if errors_mode and remaining_ids:
            await query.edit_message_text(
                f"Серия завершена!\n\n"
                f"Правильно: {correct} / {total}\n"
                f"Результат: {percentage:.0f}%\n\n"
                f"Осталось ошибочных фраз: {len(remaining_ids)}",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("Продолжить ещё 10", callback_data="pf_errors_continue")],
                    [InlineKeyboardButton("Завершить", callback_data="pf_done")]
                ])
            )
            return PF_LEARNING
        else:
            finish_text = (
                "Все ошибочные фразы проработаны! Отличная работа!\n\n"
                if errors_mode else
                "Сессия завершена!\n\n"
            )
            await query.edit_message_text(
                f"{finish_text}"
                f"Правильно: {correct}\n"
                f"Неправильно: {wrong}\n"
                f"Результат: {percentage:.0f}%\n\n"
                f"Используйте /phrases чтобы продолжить."
            )
            return ConversationHandler.END

    phrase = phrases[index]

    # Generate wrong options from the same level
    major, sub = _get_pf_level(context)
    all_phrases = get_all_phrases_flat(major, sub)
    other_phrases = [p for p in all_phrases if p["de"] != phrase["de"] and p["ru"] != phrase["ru"]]
    wrong_options = random.sample(other_phrases, min(3, len(other_phrases)))

    options = [{"text": phrase["ru"], "correct": True}]
    for p in wrong_options:
        options.append({"text": p["ru"], "correct": False})

    random.shuffle(options)

    context.user_data["pf_current_phrase"] = phrase
    context.user_data["pf_options"] = options

    keyboard = []
    for i, opt in enumerate(options):
        keyboard.append([
            InlineKeyboardButton(opt["text"], callback_data=f"pf_ans_{i}")
        ])

    errors_mode = context.user_data.get("pf_errors_mode", False)
    mode_label = "Ошибки (фразы)" if errors_mode else f"{major}.{sub}"
    context_label = f" [{phrase['context']}]" if phrase.get("context") else ""

    await query.edit_message_text(
        f"Карточка {index + 1} из {len(phrases)} | {mode_label}\n\n"
        f"{phrase['de']}{context_label}\n\n"
        f"Выберите перевод:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return PF_ANSWER


async def pf_handle_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle phrase answer selection."""
    query = update.callback_query
    await query.answer()

    answer_index = int(query.data.replace("pf_ans_", ""))
    options = context.user_data.get("pf_options", [])
    phrase = context.user_data.get("pf_current_phrase", {})
    user_id = update.effective_user.id

    is_correct = options[answer_index]["correct"]

    if is_correct:
        context.user_data["pf_correct"] = context.user_data.get("pf_correct", 0) + 1
        result_text = "Правильно!"
    else:
        context.user_data["pf_wrong"] = context.user_data.get("pf_wrong", 0) + 1
        result_text = f"Неправильно! Правильный ответ: {phrase['ru']}"

    await save_phrase_progress(
        user_id,
        phrase.get("phrase_id", ""),
        phrase.get("category_id", ""),
        is_correct
    )
    await check_and_notify_achievements(user_id, context.bot, query.message.chat_id)

    context.user_data["pf_index"] = context.user_data.get("pf_index", 0) + 1

    example = phrase.get("example", "")
    example_line = f"Пример: {example}\n" if example else ""

    await query.edit_message_text(
        f"{result_text}\n\n"
        f"{phrase['de']} — {phrase['ru']}\n"
        f"{example_line}",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Следующая фраза", callback_data="pf_next")],
            [InlineKeyboardButton("Завершить", callback_data="pf_finish")]
        ])
    )
    return PF_LEARNING


async def pf_errors_continue(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Load next batch of error phrases."""
    query = update.callback_query
    await query.answer()

    remaining_ids = context.user_data.get("pf_remaining_error_ids", [])

    if not remaining_ids:
        await query.edit_message_text(
            "Все ошибочные фразы проработаны! Отличная работа!\n\n"
            "Используйте /phrases для изучения новых фраз."
        )
        return ConversationHandler.END

    batch_ids = remaining_ids[:SESSION_SIZE]
    phrases = get_phrases_by_ids(batch_ids)

    if not phrases:
        await query.edit_message_text(
            "Не удалось загрузить фразы для повторения.\n"
            "Используйте /phrases для изучения."
        )
        return ConversationHandler.END

    context.user_data["pf_phrases"] = phrases
    context.user_data["pf_index"] = 0
    context.user_data["pf_correct"] = 0
    context.user_data["pf_wrong"] = 0
    context.user_data["pf_remaining_error_ids"] = remaining_ids[SESSION_SIZE:]

    await query.edit_message_text(
        f"Следующая серия (фразы)\n\n"
        f"Карточек: {len(phrases)}\n"
        f"Осталось после этой серии: {len(remaining_ids[SESSION_SIZE:])}\n\n"
        f"Нажмите чтобы начать!",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Начать!", callback_data="pf_next")]
        ])
    )
    return PF_LEARNING


async def pf_finish_session(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Finish phrase session early."""
    query = update.callback_query
    await query.answer()

    correct = context.user_data.get("pf_correct", 0)
    wrong = context.user_data.get("pf_wrong", 0)
    total = correct + wrong

    user_id = update.effective_user.id
    if total > 0:
        await update_daily_stats(user_id, correct=correct, total=total)

    percentage = (correct / total * 100) if total > 0 else 0

    await query.edit_message_text(
        f"Сессия завершена!\n\n"
        f"Правильно: {correct}\n"
        f"Неправильно: {wrong}\n"
        f"Результат: {percentage:.0f}%\n\n"
        f"Используйте /phrases чтобы продолжить."
    )
    return ConversationHandler.END


async def pf_done_session(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle 'done' button."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "Сессия завершена. Продолжайте в том же духе!\n\n"
        "Используйте /phrases для изучения фраз."
    )
    return ConversationHandler.END


async def pf_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel phrase session."""
    await update.message.reply_text("Изучение фраз отменено.")
    return ConversationHandler.END


def get_phrases_flashcards_handler():
    """Get the ConversationHandler for phrases flashcards."""
    return ConversationHandler(
        entry_points=[
            CommandHandler("phrases", phrases_flashcards_start),
            CallbackQueryHandler(phrases_flashcards_start, pattern="^start_phrases$"),
            CallbackQueryHandler(pf_errors_start, pattern="^pf_errors_start$")
        ],
        states={
            PF_LEVEL_SELECT: [
                CallbackQueryHandler(pf_level_selected, pattern="^pf_level_"),
                CallbackQueryHandler(pf_level_selected, pattern="^pf_cancel$")
            ],
            PF_CATEGORY_SELECT: [
                CallbackQueryHandler(pf_category_selected, pattern="^pf_cat_"),
                CallbackQueryHandler(pf_category_selected, pattern="^pf_cancel$")
            ],
            PF_LEARNING: [
                CallbackQueryHandler(pf_show_next, pattern="^pf_next$"),
                CallbackQueryHandler(pf_errors_continue, pattern="^pf_errors_continue$"),
                CallbackQueryHandler(pf_finish_session, pattern="^pf_finish$"),
                CallbackQueryHandler(pf_done_session, pattern="^pf_done$")
            ],
            PF_ANSWER: [
                CallbackQueryHandler(pf_handle_answer, pattern="^pf_ans_")
            ]
        },
        fallbacks=[CommandHandler("cancel", pf_cancel)],
        per_message=False,
        per_chat=True,
        per_user=True,
    )
