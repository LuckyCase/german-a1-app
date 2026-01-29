from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from bot.database import get_user_stats
from bot.data.vocabulary import get_all_words


async def show_progress(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user's learning progress."""
    user_id = update.effective_user.id
    stats = await get_user_stats(user_id)

    total_vocab = len(get_all_words())

    # Calculate percentages
    words_percentage = (stats["total_words"] / total_vocab * 100) if total_vocab > 0 else 0
    mastered_percentage = (stats["mastered_words"] / total_vocab * 100) if total_vocab > 0 else 0

    if stats["total_correct"] + stats["total_wrong"] > 0:
        accuracy = stats["total_correct"] / (stats["total_correct"] + stats["total_wrong"]) * 100
    else:
        accuracy = 0

    if stats["grammar_total"] > 0:
        grammar_accuracy = stats["grammar_score"] / stats["grammar_total"] * 100
    else:
        grammar_accuracy = 0

    # Create progress bars
    def progress_bar(percentage, length=10):
        filled = int(percentage / 100 * length)
        empty = length - filled
        return "█" * filled + "░" * empty

    message = (
        f"📊 Ваш прогресс в изучении немецкого A1\n"
        f"{'═' * 35}\n\n"
        f"📚 Словарный запас:\n"
        f"   Изучено слов: {stats['total_words']} из {total_vocab}\n"
        f"   {progress_bar(words_percentage)} {words_percentage:.0f}%\n\n"
        f"⭐ Освоено (без ошибок):\n"
        f"   {stats['mastered_words']} слов\n"
        f"   {progress_bar(mastered_percentage)} {mastered_percentage:.0f}%\n\n"
        f"📝 Карточки:\n"
        f"   Правильно: {stats['total_correct']}\n"
        f"   Неправильно: {stats['total_wrong']}\n"
        f"   Точность: {accuracy:.0f}%\n\n"
        f"📖 Грамматика:\n"
        f"   Тестов пройдено: {stats['tests_completed']}\n"
        f"   Баллы: {stats['grammar_score']} из {stats['grammar_total']}\n"
        f"   Точность: {grammar_accuracy:.0f}%\n\n"
    )

    # Add motivation message
    if words_percentage < 25:
        motivation = "🌱 Отличное начало! Продолжайте учить новые слова!"
    elif words_percentage < 50:
        motivation = "🌿 Хороший прогресс! Вы на правильном пути!"
    elif words_percentage < 75:
        motivation = "🌳 Отлично! Больше половины пути пройдено!"
    elif words_percentage < 100:
        motivation = "🏆 Почти готово! Ещё немного до цели!"
    else:
        motivation = "🎉 Поздравляем! Весь словарь изучен!"

    message += motivation

    keyboard = [
        [InlineKeyboardButton("🔄 Обновить", callback_data="progress_refresh")],
        [InlineKeyboardButton("📚 Учить слова", callback_data="start_flashcards")],
        [InlineKeyboardButton("📝 Грамматика", callback_data="start_grammar")]
    ]

    await update.message.reply_text(message, reply_markup=InlineKeyboardMarkup(keyboard))


async def progress_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle progress-related callbacks."""
    query = update.callback_query
    await query.answer()

    if query.data == "progress_refresh":
        user_id = update.effective_user.id
        stats = await get_user_stats(user_id)
        total_vocab = len(get_all_words())

        words_percentage = (stats["total_words"] / total_vocab * 100) if total_vocab > 0 else 0
        mastered_percentage = (stats["mastered_words"] / total_vocab * 100) if total_vocab > 0 else 0

        if stats["total_correct"] + stats["total_wrong"] > 0:
            accuracy = stats["total_correct"] / (stats["total_correct"] + stats["total_wrong"]) * 100
        else:
            accuracy = 0

        if stats["grammar_total"] > 0:
            grammar_accuracy = stats["grammar_score"] / stats["grammar_total"] * 100
        else:
            grammar_accuracy = 0

        def progress_bar(percentage, length=10):
            filled = int(percentage / 100 * length)
            empty = length - filled
            return "█" * filled + "░" * empty

        message = (
            f"📊 Ваш прогресс в изучении немецкого A1\n"
            f"{'═' * 35}\n\n"
            f"📚 Словарный запас:\n"
            f"   Изучено слов: {stats['total_words']} из {total_vocab}\n"
            f"   {progress_bar(words_percentage)} {words_percentage:.0f}%\n\n"
            f"⭐ Освоено (без ошибок):\n"
            f"   {stats['mastered_words']} слов\n"
            f"   {progress_bar(mastered_percentage)} {mastered_percentage:.0f}%\n\n"
            f"📝 Карточки:\n"
            f"   Правильно: {stats['total_correct']}\n"
            f"   Неправильно: {stats['total_wrong']}\n"
            f"   Точность: {accuracy:.0f}%\n\n"
            f"📖 Грамматика:\n"
            f"   Тестов пройдено: {stats['tests_completed']}\n"
            f"   Баллы: {stats['grammar_score']} из {stats['grammar_total']}\n"
            f"   Точность: {grammar_accuracy:.0f}%\n\n"
            f"(Обновлено)"
        )

        keyboard = [
            [InlineKeyboardButton("🔄 Обновить", callback_data="progress_refresh")],
            [InlineKeyboardButton("📚 Учить слова", callback_data="start_flashcards")],
            [InlineKeyboardButton("📝 Грамматика", callback_data="start_grammar")]
        ]

        await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data == "start_flashcards":
        await query.edit_message_text("Используйте команду /flashcards чтобы начать изучение слов.")

    elif query.data == "start_grammar":
        await query.edit_message_text("Используйте команду /grammar чтобы пройти грамматический тест.")
