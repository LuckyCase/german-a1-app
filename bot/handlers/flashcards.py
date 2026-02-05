import random
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, CallbackQueryHandler

from bot.content_manager import (
    get_all_words, get_words_by_category, get_categories,
    get_current_level_str, get_levels_with_content, set_level
)
from bot.database import update_word_progress, update_daily_stats
from bot.handlers.audio import send_word_audio

# Conversation states
LEVEL_SELECT, CATEGORY_SELECT, LEARNING, ANSWER = range(4)


async def flashcards_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start flashcards learning session."""
    try:
        # Проверяем, есть ли несколько уровней с контентом
        levels = get_levels_with_content()
        
        if len(levels) > 1:
            # Показываем выбор уровня
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
            # Только один уровень - сразу показываем категории
            return await show_categories(update, context)
            
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Error in flashcards_start: {e}", exc_info=True)
        error_text = f"Произошла ошибка: {str(e)}"
        try:
            if update.message:
                await update.message.reply_text(error_text)
            elif update.callback_query:
                await update.callback_query.answer()
                await update.callback_query.edit_message_text(error_text)
        except:
            pass
        return ConversationHandler.END


async def level_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle level selection."""
    query = update.callback_query
    await query.answer()

    if query.data == "fc_cancel":
        await query.edit_message_text("Изучение отменено. Используйте /flashcards чтобы начать снова.")
        return ConversationHandler.END

    # Парсим выбранный уровень
    parts = query.data.replace("fc_level_", "").split("_")
    if len(parts) == 2:
        major, sub = parts
        set_level(major, sub)
        context.user_data["fc_level"] = (major, sub)
    
    return await show_categories(update, context)


async def show_categories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show categories for current level."""
    try:
        categories = get_categories()

        if not categories:
            error_text = f"Категории для уровня {get_current_level_str()} не найдены."
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
        text = f"Уровень: {get_current_level_str()}\n\nВыберите категорию для изучения:"

        if update.message:
            await update.message.reply_text(text, reply_markup=reply_markup)
        elif update.callback_query:
            await update.callback_query.edit_message_text(text, reply_markup=reply_markup)
        
        return CATEGORY_SELECT
        
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Error in show_categories: {e}", exc_info=True)
        error_text = f"Произошла ошибка: {str(e)}"
        try:
            if update.message:
                await update.message.reply_text(error_text)
            elif update.callback_query:
                await update.callback_query.edit_message_text(error_text)
        except:
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

    if category_id == "all":
        words = get_all_words()
        context.user_data["fc_category_name"] = "Все слова"
    else:
        words = get_words_by_category(category_id)
        # Получаем название категории из первого слова
        if words:
            context.user_data["fc_category_name"] = words[0].get("category_name", category_id)
        else:
            context.user_data["fc_category_name"] = category_id

    random.shuffle(words)
    context.user_data["fc_words"] = words
    context.user_data["fc_index"] = 0
    context.user_data["fc_correct"] = 0
    context.user_data["fc_wrong"] = 0

    await query.edit_message_text(
        f"Уровень: {get_current_level_str()}\n"
        f"Категория: {context.user_data['fc_category_name']}\n"
        f"Слов: {len(words)}\n\n"
        f"Готовы? Нажмите кнопку ниже!",
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
            pass  # Message already deleted or unavailable
        context.user_data.pop("fc_audio_message_id", None)

    words = context.user_data.get("fc_words", [])
    index = context.user_data.get("fc_index", 0)

    if index >= len(words):
        # Session complete
        # Delete audio message if exists
        audio_msg_id = context.user_data.get("fc_audio_message_id")
        if audio_msg_id:
            try:
                await context.bot.delete_message(
                    chat_id=query.message.chat_id,
                    message_id=audio_msg_id
                )
            except Exception:
                pass  # Message already deleted or unavailable
            context.user_data.pop("fc_audio_message_id", None)

        correct = context.user_data.get("fc_correct", 0)
        wrong = context.user_data.get("fc_wrong", 0)
        total = correct + wrong

        user_id = update.effective_user.id
        await update_daily_stats(user_id, words=correct, correct=correct, total=total)

        percentage = (correct / total * 100) if total > 0 else 0

        await query.edit_message_text(
            f"Сессия завершена!\n\n"
            f"Уровень: {get_current_level_str()}\n"
            f"Правильно: {correct}\n"
            f"Неправильно: {wrong}\n"
            f"Результат: {percentage:.0f}%\n\n"
            f"Используйте /flashcards чтобы продолжить изучение."
        )
        return ConversationHandler.END

    word = words[index]

    # Generate wrong options
    all_words = get_all_words()
    other_words = [w for w in all_words if w["de"] != word["de"]]
    wrong_options = random.sample(other_words, min(3, len(other_words)))

    options = [{"text": word["ru"], "correct": True}]
    for w in wrong_options:
        options.append({"text": w["ru"], "correct": False})

    random.shuffle(options)

    # Store correct answer
    context.user_data["fc_current_word"] = word
    context.user_data["fc_options"] = options

    keyboard = []
    for i, opt in enumerate(options):
        keyboard.append([
            InlineKeyboardButton(opt["text"], callback_data=f"fc_ans_{i}")
        ])

    keyboard.append([InlineKeyboardButton("Прослушать", callback_data="fc_audio")])

    await query.edit_message_text(
        f"Слово {index + 1} из {len(words)}\n\n"
        f"{word['de']}\n\n"
        f"Выберите перевод:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return ANSWER


async def handle_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle answer selection."""
    query = update.callback_query
    await query.answer()

    if query.data == "fc_audio":
        word = context.user_data.get("fc_current_word", {})
        # Delete previous audio message if exists
        audio_msg_id = context.user_data.get("fc_audio_message_id")
        if audio_msg_id:
            try:
                await context.bot.delete_message(
                    chat_id=query.message.chat_id,
                    message_id=audio_msg_id
                )
            except Exception:
                pass  # Message already deleted or unavailable
        
        # Send new audio and save message_id
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

    # Update progress in database
    await update_word_progress(user_id, word.get("word_id", ""), is_correct)

    context.user_data["fc_index"] = context.user_data.get("fc_index", 0) + 1

    await query.edit_message_text(
        f"{result_text}\n\n"
        f"{word['de']} - {word['ru']}\n"
        f"Пример: {word.get('example', '')}\n\n",
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
    # Delete previous audio message if exists
    audio_msg_id = context.user_data.get("fc_audio_message_id")
    if audio_msg_id:
        try:
            await context.bot.delete_message(
                chat_id=query.message.chat_id,
                message_id=audio_msg_id
            )
        except Exception:
            pass  # Message already deleted or unavailable
    
    # Send new audio and save message_id
    audio_message = await send_word_audio(update, context, word.get("de", ""))
    if audio_message:
        context.user_data["fc_audio_message_id"] = audio_message.message_id
    return LEARNING


async def finish_session(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Finish the learning session early."""
    query = update.callback_query
    await query.answer()

    # Delete audio message if exists
    audio_msg_id = context.user_data.get("fc_audio_message_id")
    if audio_msg_id:
        try:
            await context.bot.delete_message(
                chat_id=query.message.chat_id,
                message_id=audio_msg_id
            )
        except Exception:
            pass  # Message already deleted or unavailable
        context.user_data.pop("fc_audio_message_id", None)

    correct = context.user_data.get("fc_correct", 0)
    wrong = context.user_data.get("fc_wrong", 0)
    total = correct + wrong

    user_id = update.effective_user.id
    if total > 0:
        await update_daily_stats(user_id, words=correct, correct=correct, total=total)

    percentage = (correct / total * 100) if total > 0 else 0

    await query.edit_message_text(
        f"Сессия завершена!\n\n"
        f"Уровень: {get_current_level_str()}\n"
        f"Правильно: {correct}\n"
        f"Неправильно: {wrong}\n"
        f"Результат: {percentage:.0f}%\n\n"
        f"Используйте /flashcards чтобы продолжить изучение."
    )
    return ConversationHandler.END


async def cancel_flashcards(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel flashcards session."""
    await update.message.reply_text("Изучение отменено.")
    return ConversationHandler.END


def get_flashcards_handler():
    """Get the ConversationHandler for flashcards."""
    return ConversationHandler(
        entry_points=[CommandHandler("flashcards", flashcards_start)],
        states={
            LEVEL_SELECT: [
                CallbackQueryHandler(level_selected, pattern="^fc_level_"),
                CallbackQueryHandler(level_selected, pattern="^fc_cancel$")
            ],
            CATEGORY_SELECT: [
                CallbackQueryHandler(category_selected, pattern="^fc_cat_")
            ],
            LEARNING: [
                CallbackQueryHandler(show_next_word, pattern="^fc_next$"),
                CallbackQueryHandler(handle_audio_result, pattern="^fc_audio_result$"),
                CallbackQueryHandler(finish_session, pattern="^fc_finish$")
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
