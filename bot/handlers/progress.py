from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from bot.database import get_user_stats
from bot.content_manager import get_all_words


def _progress_bar(percentage: float, length: int = 10) -> str:
    filled = int(percentage / 100 * length)
    empty = length - filled
    return "█" * filled + "░" * empty


def _build_stats_text(stats: dict, total_vocab: int, suffix: str = "") -> str:
    words_pct = (stats["total_words"] / total_vocab * 100) if total_vocab > 0 else 0
    mastered_pct = (stats["mastered_words"] / total_vocab * 100) if total_vocab > 0 else 0

    total_answers = stats["total_correct"] + stats["total_wrong"]
    accuracy = (stats["total_correct"] / total_answers * 100) if total_answers > 0 else 0

    grammar_accuracy = (
        stats["grammar_score"] / stats["grammar_total"] * 100
        if stats["grammar_total"] > 0 else 0
    )

    errors_line = (
        f"   ⚠️ Требуют повторения: {stats['words_with_errors']} слов\n"
        if stats.get("words_with_errors", 0) > 0 else ""
    )

    if words_pct < 25:
        motivation = "🌱 Отличное начало! Продолжайте учить новые слова!"
    elif words_pct < 50:
        motivation = "🌿 Хороший прогресс! Вы на правильном пути!"
    elif words_pct < 75:
        motivation = "🌳 Отлично! Больше половины пути пройдено!"
    elif words_pct < 100:
        motivation = "🏆 Почти готово! Ещё немного до цели!"
    else:
        motivation = "🎉 Поздравляем! Весь словарь изучен!"

    return (
        f"📊 Ваш прогресс в изучении немецкого\n"
        f"{'═' * 35}\n\n"
        f"📚 Словарный запас:\n"
        f"   Изучено слов: {stats['total_words']} из {total_vocab}\n"
        f"   {_progress_bar(words_pct)} {words_pct:.0f}%\n\n"
        f"⭐ Освоено (без ошибок):\n"
        f"   {stats['mastered_words']} слов\n"
        f"   {_progress_bar(mastered_pct)} {mastered_pct:.0f}%\n\n"
        f"{errors_line}"
        f"📝 Карточки:\n"
        f"   Правильно: {stats['total_correct']}\n"
        f"   Неправильно: {stats['total_wrong']}\n"
        f"   Точность: {accuracy:.0f}%\n\n"
        f"📖 Грамматика:\n"
        f"   Тестов пройдено: {stats['tests_completed']}\n"
        f"   Баллы: {stats['grammar_score']} из {stats['grammar_total']}\n"
        f"   Точность: {grammar_accuracy:.0f}%\n\n"
        f"{motivation}"
        f"{suffix}"
    )


def _build_keyboard(has_errors: bool) -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("🔄 Обновить", callback_data="progress_refresh")],
        [InlineKeyboardButton("📚 Учить слова", callback_data="start_flashcards")],
        [InlineKeyboardButton("💬 Учить фразы", callback_data="start_phrases")],
        [InlineKeyboardButton("📝 Грамматика", callback_data="start_grammar")]
    ]
    if has_errors:
        keyboard.insert(1, [
            InlineKeyboardButton("🔁 Работа над ошибками", callback_data="fc_errors_start")
        ])
    return InlineKeyboardMarkup(keyboard)


async def show_progress(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user's learning progress."""
    user_id = update.effective_user.id
    stats = await get_user_stats(user_id)
    total_vocab = len(get_all_words())

    has_errors = stats.get("words_with_errors", 0) > 0
    text = _build_stats_text(stats, total_vocab)

    await update.message.reply_text(text, reply_markup=_build_keyboard(has_errors))


async def progress_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle progress-related callbacks."""
    query = update.callback_query
    await query.answer()

    if query.data == "progress_refresh":
        user_id = update.effective_user.id
        stats = await get_user_stats(user_id)
        total_vocab = len(get_all_words())

        has_errors = stats.get("words_with_errors", 0) > 0
        text = _build_stats_text(stats, total_vocab, suffix="\n(Обновлено)")

        await query.edit_message_text(text, reply_markup=_build_keyboard(has_errors))

    elif query.data == "start_flashcards":
        from bot.handlers.flashcards import flashcards_start
        await flashcards_start(update, context)

    elif query.data == "start_phrases":
        from bot.handlers.phrases_flashcards import phrases_flashcards_start
        await phrases_flashcards_start(update, context)

    elif query.data == "start_grammar":
        from bot.handlers.grammar import grammar_start
        await grammar_start(update, context)
