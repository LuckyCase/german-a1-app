import random
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, CallbackQueryHandler

from bot.content_manager import (
    get_all_words, get_words_by_category, get_categories,
    get_current_level, get_current_level_str, get_levels_with_content, set_level,
    get_words_by_ids
)
from bot.database import (
    update_word_progress, update_daily_stats,
    get_priority_word_ids, get_all_error_word_ids
)
from bot.handlers.audio import send_word_audio

logger = logging.getLogger(__name__)

# Conversation states
LEVEL_SELECT, CATEGORY_SELECT, LEARNING, ANSWER = range(4)

SESSION_SIZE = 10
MAX_ERROR_WORDS = 5


def _get_fc_level(context) -> tuple:
    """Get level from user session, falling back to global current level."""
    return context.user_data.get("fc_level", get_current_level())


async def _build_session_words(user_id: int, words: list) -> list:
    """Build a session of up to SESSION_SIZE words.

    Up to MAX_ERROR_WORDS slots are filled with words the user previously
    got wrong (ordered by error count). Remaining slots are filled with
    random words from the rest.
    """
    if not words:
        return []

    word_ids = [w["word_id"] for w in words]
    error_ids = await get_priority_word_ids(user_id, word_ids)

    # Build lookup map
    word_map = {w["word_id"]: w for w in words}

    # Take up to MAX_ERROR_WORDS error words (already sorted by priority)
    error_words = [word_map[wid] for wid in error_ids[:MAX_ERROR_WORDS] if wid in word_map]

    # Fill remaining slots with random non-error words
    error_id_set = set(wid for wid in error_ids[:MAX_ERROR_WORDS])
    remaining = [w for w in words if w["word_id"] not in error_id_set]
    random.shuffle(remaining)
    fill_count = SESSION_SIZE - len(error_words)
    new_words = remaining[:fill_count]

    session = error_words + new_words
    random.shuffle(session)
    return session


async def flashcards_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start flashcards learning session."""
    try:
        # Store current level as default (overridden if user picks another)
        context.user_data["fc_level"] = get_current_level()

        levels = get_levels_with_content()

        if len(levels) > 1:
            keyboard = []
            for level in levels:
                keyboard.append([
                    InlineKeyboardButton(
                        f"{'✓ ' if level['is_current'] else ''}{level['display_name']}",
                        callback_data=f"fc_level_{level['major']}_{level['sub']}"
                    )
                ])
            keyboard.append([InlineKeyboardButton("Отмена", callback_data="fc_cancel")])

            reply_markup = InlineKeyboardMarkup(keyboard)

            if update.message:
                await update.message.reply_text(
                    f"Текущий уровень: {get_current_level_str()}\n\n"
                    "Выберите уровень для изучения:",
                    reply_markup=reply_markup
                )
            elif update.callback_query:
                await update.callback_query.answer()
                await update.callback_query.edit_message_text(
                    f"Текущий уровень: {get_current_level_str()}\n\n"
                    "Выберите уровень для изучения:",
                    reply_markup=reply_markup
                )
            return LEVEL_SELECT
        else:
            return await show_categories(update, context)

    except Exception as e:
        logger.error(f"Error in flashcards_start: {e}", exc_info=True)
        error_text = f"Произошла ошибка: {str(e)}"
        try:
            if update.message:
                await update.message.reply_text(error_text)
            elif update.callback_query:
                await update.callback_query.answer()
                await update.callback_query.edit_message_text(error_text)
        except Exception:
            pass
        return ConversationHandler.END


async def level_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle level selection."""
    query = update.callback_query
    await query.answer()

    if query.data == "fc_cancel":
        await query.edit_message_text("Изучение отменено. Используйте /flashcards чтобы начать снова.")
        return ConversationHandler.END

    parts = query.data.replace("fc_level_", "").split("_")
    if len(parts) == 2:
        major, sub = parts
        set_level(major, sub)
        context.user_data["fc_level"] = (major, sub)

    return await show_categories(update, context)


async def show_categories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show categories for current level."""
    try:
        major, sub = _get_fc_level(context)
        level_str = f"{major}.{sub}"
        categories = get_categories(major, sub)

        if not categories:
            error_text = f"Категории для уровня {level_str} не найдены."
            if update.message:
                await update.message.reply_text(error_text)
            elif update.callback_query:
                await update.callback_query.edit_message_text(error_text)
            return ConversationHandler.END

        keyboard = []
        for cat in categories:
            keyboard.append([
                InlineKeyboardButton(
                    f"{cat['name']} ({cat['count']} слов)",
                    callback_data=f"fc_cat_{cat['id']}"
                )
            ])
        keyboard.append([InlineKeyboardButton("Все слова (случайно)", callback_data="fc_cat_all")])
        keyboard.append([InlineKeyboardButton("Отмена", callback_data="fc_cancel")])

        reply_markup = InlineKeyboardMarkup(keyboard)
        text = f"Уровень: {level_str}\n\nВыберите категорию для изучения:"

        if update.message:
            await update.message.reply_text(text, reply_markup=reply_markup)
        elif update.callback_query:
            await update.callback_query.edit_message_text(text, reply_markup=reply_markup)

        return CATEGORY_SELECT

    except Exception as e:
        logger.error(f"Error in show_categories: {e}", exc_info=True)
        error_text = f"Произошла ошибка: {str(e)}"
        try:
            if update.message:
                await update.message.reply_text(error_text)
            elif update.callback_query:
                await update.callback_query.edit_message_text(error_text)
        except Exception:
            pass
        return ConversationHandler.END


async def category_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle category selection."""
    query = update.callback_query
    await query.answer()

    if query.data == "fc_cancel":
        await query.edit_message_text("Изучение отменено. Используйте /flashcards чтобы начать снова.")
        return ConversationHandler.END

    category_id = query.data.replace("fc_cat_", "")
    user_id = update.effective_user.id
    major, sub = _get_fc_level(context)

    if category_id == "all":
        words = get_all_words(major, sub)
        context.user_data["fc_category_name"] = "Все слова"
    else:
        words = get_words_by_category(category_id, major, sub)
        if words:
            context.user_data["fc_category_name"] = words[0].get("category_name", category_id)
        else:
            context.user_data["fc_category_name"] = category_id

    session = await _build_session_words(user_id, words)

    context.user_data["fc_words"] = session
    context.user_data["fc_index"] = 0
    context.user_data["fc_correct"] = 0
    context.user_data["fc_wrong"] = 0
    context.user_data["fc_errors_mode"] = False

    level_str = f"{major}.{sub}"
    await query.edit_message_text(
        f"Уровень: {level_str}\n"
        f"Категория: {context.user_data['fc_category_name']}\n"
        f"Карточек в сессии: {len(session)}\n\n"
        f"Готовы? Нажмите кнопку ниже!",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Начать!", callback_data="fc_next")]
        ])
    )
    return LEARNING


# ──────────────────────────────────────────────
# Режим "Работа над ошибками"
# ──────────────────────────────────────────────

async def errors_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start error-review mode: show words with mistakes from ALL categories."""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    error_ids = await get_all_error_word_ids(user_id)

    if not error_ids:
        await query.edit_message_text(
            "Отлично! Ошибок нет.\n\n"
            "Используйте /flashcards для изучения новых слов."
        )
        return ConversationHandler.END

    # Load first batch of up to SESSION_SIZE error words
    batch_ids = error_ids[:SESSION_SIZE]
    words = get_words_by_ids(batch_ids)

    if not words:
        await query.edit_message_text(
            "Не удалось загрузить слова для повторения.\n"
            "Используйте /flashcards для изучения."
        )
        return ConversationHandler.END

    context.user_data["fc_words"] = words
    context.user_data["fc_index"] = 0
    context.user_data["fc_correct"] = 0
    context.user_data["fc_wrong"] = 0
    context.user_data["fc_errors_mode"] = True
    # Store remaining error_ids (after this batch) for "continue"
    context.user_data["fc_remaining_error_ids"] = error_ids[SESSION_SIZE:]

    await query.edit_message_text(
        f"Работа над ошибками\n\n"
        f"Слов для повторения: {len(error_ids)}\n"
        f"Карточек в этой серии: {len(words)}\n\n"
        f"Нажмите чтобы начать!",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Начать!", callback_data="fc_next")]
        ])
    )
    return LEARNING


async def show_next_word(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show the next word to learn."""
    query = update.callback_query
    await query.answer()

    # Delete previous audio message if exists
    audio_msg_id = context.user_data.get("fc_audio_message_id")
    if audio_msg_id:
        try:
            await context.bot.delete_message(
                chat_id=query.message.chat_id,
                message_id=audio_msg_id
            )
        except Exception:
            pass
        context.user_data.pop("fc_audio_message_id", None)

    words = context.user_data.get("fc_words", [])
    index = context.user_data.get("fc_index", 0)

    if index >= len(words):
        # Session complete
        correct = context.user_data.get("fc_correct", 0)
        wrong = context.user_data.get("fc_wrong", 0)
        total = correct + wrong

        user_id = update.effective_user.id
        await update_daily_stats(user_id, words=correct, correct=correct, total=total)

        percentage = (correct / total * 100) if total > 0 else 0
        errors_mode = context.user_data.get("fc_errors_mode", False)
        remaining_ids = context.user_data.get("fc_remaining_error_ids", [])

        if errors_mode and remaining_ids:
            await query.edit_message_text(
                f"Серия завершена!\n\n"
                f"Правильно: {correct} / {total}\n"
                f"Результат: {percentage:.0f}%\n\n"
                f"Осталось ошибочных слов: {len(remaining_ids)}",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("Продолжить ещё 10", callback_data="fc_errors_continue")],
                    [InlineKeyboardButton("Завершить", callback_data="fc_done")]
                ])
            )
            return LEARNING
        else:
            finish_text = (
                "Все ошибочные слова проработаны! Отличная работа!\n\n"
                if errors_mode else
                "Сессия завершена!\n\n"
            )
            fc_major, fc_sub = _get_fc_level(context)
            await query.edit_message_text(
                f"{finish_text}"
                f"Уровень: {fc_major}.{fc_sub}\n"
                f"Правильно: {correct}\n"
                f"Неправильно: {wrong}\n"
                f"Результат: {percentage:.0f}%\n\n"
                f"Используйте /flashcards чтобы продолжить изучение."
            )
            return ConversationHandler.END

    word = words[index]

    # Generate wrong options from the same level
    major, sub = _get_fc_level(context)
    all_words = get_all_words(major, sub)
    other_words = [w for w in all_words if w["de"] != word["de"] and w["ru"] != word["ru"]]
    wrong_options = random.sample(other_words, min(3, len(other_words)))

    options = [{"text": word["ru"], "correct": True}]
    for w in wrong_options:
        options.append({"text": w["ru"], "correct": False})

    random.shuffle(options)

    context.user_data["fc_current_word"] = word
    context.user_data["fc_options"] = options

    keyboard = []
    for i, opt in enumerate(options):
        keyboard.append([
            InlineKeyboardButton(opt["text"], callback_data=f"fc_ans_{i}")
        ])
    keyboard.append([InlineKeyboardButton("Прослушать", callback_data="fc_audio")])

    errors_mode = context.user_data.get("fc_errors_mode", False)
    mode_label = "Ошибки" if errors_mode else f"{major}.{sub}"

    await query.edit_message_text(
        f"Карточка {index + 1} из {len(words)} | {mode_label}\n\n"
        f"{word['de']}\n\n"
        f"Выберите перевод:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return ANSWER


async def errors_continue(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Load next batch of error words."""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    remaining_ids = context.user_data.get("fc_remaining_error_ids", [])

    if not remaining_ids:
        await query.edit_message_text(
            "Все ошибочные слова проработаны! Отличная работа!\n\n"
            "Используйте /flashcards для изучения новых слов."
        )
        return ConversationHandler.END

    batch_ids = remaining_ids[:SESSION_SIZE]
    words = get_words_by_ids(batch_ids)

    if not words:
        await query.edit_message_text(
            "Не удалось загрузить слова для повторения.\n"
            "Используйте /flashcards для изучения."
        )
        return ConversationHandler.END

    context.user_data["fc_words"] = words
    context.user_data["fc_index"] = 0
    context.user_data["fc_correct"] = 0
    context.user_data["fc_wrong"] = 0
    context.user_data["fc_remaining_error_ids"] = remaining_ids[SESSION_SIZE:]

    await query.edit_message_text(
        f"Следующая серия\n\n"
        f"Карточек: {len(words)}\n"
        f"Осталось после этой серии: {len(remaining_ids[SESSION_SIZE:])}\n\n"
        f"Нажмите чтобы начать!",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Начать!", callback_data="fc_next")]
        ])
    )
    return LEARNING


async def handle_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle answer selection."""
    query = update.callback_query
    await query.answer()

    if query.data == "fc_audio":
        word = context.user_data.get("fc_current_word", {})
        audio_msg_id = context.user_data.get("fc_audio_message_id")
        if audio_msg_id:
            try:
                await context.bot.delete_message(
                    chat_id=query.message.chat_id,
                    message_id=audio_msg_id
                )
            except Exception:
                pass

        audio_message = await send_word_audio(update, context, word.get("de", ""))
        if audio_message:
            context.user_data["fc_audio_message_id"] = audio_message.message_id
        return ANSWER

    answer_index = int(query.data.replace("fc_ans_", ""))
    options = context.user_data.get("fc_options", [])
    word = context.user_data.get("fc_current_word", {})
    user_id = update.effective_user.id

    is_correct = options[answer_index]["correct"]

    if is_correct:
        context.user_data["fc_correct"] = context.user_data.get("fc_correct", 0) + 1
        result_text = "Правильно!"
    else:
        context.user_data["fc_wrong"] = context.user_data.get("fc_wrong", 0) + 1
        result_text = f"Неправильно! Правильный ответ: {word['ru']}"

    await update_word_progress(user_id, word.get("word_id", ""), is_correct)

    context.user_data["fc_index"] = context.user_data.get("fc_index", 0) + 1

    await query.edit_message_text(
        f"{result_text}\n\n"
        f"{word['de']} — {word['ru']}\n"
        f"Пример: {word.get('example', '')}\n",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Следующее слово", callback_data="fc_next")],
            [InlineKeyboardButton("Прослушать", callback_data="fc_audio_result")],
            [InlineKeyboardButton("Завершить", callback_data="fc_finish")]
        ])
    )
    return LEARNING


async def handle_audio_result(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle audio request on result screen."""
    query = update.callback_query
    await query.answer()

    word = context.user_data.get("fc_current_word", {})
    audio_msg_id = context.user_data.get("fc_audio_message_id")
    if audio_msg_id:
        try:
            await context.bot.delete_message(
                chat_id=query.message.chat_id,
                message_id=audio_msg_id
            )
        except Exception:
            pass

    audio_message = await send_word_audio(update, context, word.get("de", ""))
    if audio_message:
        context.user_data["fc_audio_message_id"] = audio_message.message_id
    return LEARNING


async def finish_session(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Finish the learning session early."""
    query = update.callback_query
    await query.answer()

    audio_msg_id = context.user_data.get("fc_audio_message_id")
    if audio_msg_id:
        try:
            await context.bot.delete_message(
                chat_id=query.message.chat_id,
                message_id=audio_msg_id
            )
        except Exception:
            pass
        context.user_data.pop("fc_audio_message_id", None)

    correct = context.user_data.get("fc_correct", 0)
    wrong = context.user_data.get("fc_wrong", 0)
    total = correct + wrong

    user_id = update.effective_user.id
    if total > 0:
        await update_daily_stats(user_id, words=correct, correct=correct, total=total)

    percentage = (correct / total * 100) if total > 0 else 0

    major, sub = _get_fc_level(context)
    await query.edit_message_text(
        f"Сессия завершена!\n\n"
        f"Уровень: {major}.{sub}\n"
        f"Правильно: {correct}\n"
        f"Неправильно: {wrong}\n"
        f"Результат: {percentage:.0f}%\n\n"
        f"Используйте /flashcards чтобы продолжить изучение."
    )
    return ConversationHandler.END


async def done_session(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle 'done' button in error-review mode."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "Сессия завершена. Продолжайте в том же духе!\n\n"
        "Используйте /flashcards для изучения новых слов."
    )
    return ConversationHandler.END


async def cancel_flashcards(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel flashcards session."""
    await update.message.reply_text("Изучение отменено.")
    return ConversationHandler.END


def get_flashcards_handler():
    """Get the ConversationHandler for flashcards."""
    return ConversationHandler(
        entry_points=[
            CommandHandler("flashcards", flashcards_start),
            CallbackQueryHandler(flashcards_start, pattern="^start_flashcards$"),
            CallbackQueryHandler(errors_start, pattern="^fc_errors_start$")
        ],
        states={
            LEVEL_SELECT: [
                CallbackQueryHandler(level_selected, pattern="^fc_level_"),
                CallbackQueryHandler(level_selected, pattern="^fc_cancel$")
            ],
            CATEGORY_SELECT: [
                CallbackQueryHandler(category_selected, pattern="^fc_cat_"),
                CallbackQueryHandler(category_selected, pattern="^fc_cancel$")
            ],
            LEARNING: [
                CallbackQueryHandler(show_next_word, pattern="^fc_next$"),
                CallbackQueryHandler(errors_continue, pattern="^fc_errors_continue$"),
                CallbackQueryHandler(handle_audio_result, pattern="^fc_audio_result$"),
                CallbackQueryHandler(finish_session, pattern="^fc_finish$"),
                CallbackQueryHandler(done_session, pattern="^fc_done$")
            ],
            ANSWER: [
                CallbackQueryHandler(handle_answer, pattern="^fc_ans_"),
                CallbackQueryHandler(handle_answer, pattern="^fc_audio$")
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel_flashcards)],
        per_message=False,
        per_chat=True,
        per_user=True,
    )
