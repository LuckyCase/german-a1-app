from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from bot.database import get_user_stats, get_user_streak, get_user_achievements, get_user_settings
from bot.content_manager import get_all_words, get_levels_with_content
from bot.achievements import get_achievement_display


def _get_total_vocab() -> int:
    """Count total vocabulary across all levels with content."""
    total = 0
    for level in get_levels_with_content():
        total += len(get_all_words(level["major"], level["sub"]))
    return total


def _get_total_vocab_for_major(major: str) -> int:
    """Count total vocabulary for a major CEFR block (e.g. A1)."""
    total = 0
    for level in get_levels_with_content():
        if level["major"] == major:
            total += len(get_all_words(level["major"], level["sub"]))
    return total


def _progress_bar(percentage: float, length: int = 10) -> str:
    filled = int(percentage / 100 * length)
    empty = length - filled
    return "█" * filled + "░" * empty


def _build_stats_text(stats: dict, total_vocab: int, suffix: str = "",
                      streak: int = 0, achievements: list = None) -> str:
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
    phrase_errors_line = (
        f"   ⚠️ Фразы с ошибками: {stats['phrases_with_errors']}\n"
        if stats.get("phrases_with_errors", 0) > 0 else ""
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

    streak_line = f"🔥 Серия: {streak} {'день' if streak == 1 else 'дней'} подряд\n\n" if streak > 0 else ""
    ach_display = get_achievement_display(achievements or [])
    ach_block = f"\n🏅 Достижения:\n{ach_display}\n" if ach_display else ""

    return (
        f"📊 Ваш прогресс в изучении немецкого\n"
        f"{'═' * 35}\n\n"
        f"{streak_line}"
        f"📚 Словарный запас:\n"
        f"   Изучено слов: {stats['total_words']} из {total_vocab}\n"
        f"   {_progress_bar(words_pct)} {words_pct:.0f}%\n\n"
        f"⭐ Освоено (без ошибок):\n"
        f"   {stats['mastered_words']} слов\n"
        f"   {_progress_bar(mastered_pct)} {mastered_pct:.0f}%\n\n"
        f"{errors_line}"
        f"{phrase_errors_line}"
        f"📝 Карточки:\n"
        f"   Правильно: {stats['total_correct']}\n"
        f"   Неправильно: {stats['total_wrong']}\n"
        f"   Точность: {accuracy:.0f}%\n\n"
        f"📖 Грамматика:\n"
        f"   Тестов пройдено: {stats['tests_completed']}\n"
        f"   Баллы: {stats['grammar_score']} из {stats['grammar_total']}\n"
        f"   Точность: {grammar_accuracy:.0f}%\n\n"
        f"{motivation}"
        f"{ach_block}"
        f"{suffix}"
    )


def _build_keyboard(has_word_errors: bool, has_phrase_errors: bool, show_a2_upgrade: bool = False) -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("🔄 Обновить", callback_data="progress_refresh")],
        [InlineKeyboardButton("📚 Учить слова", callback_data="start_flashcards")],
        [InlineKeyboardButton("💬 Учить фразы", callback_data="start_phrases")],
        [InlineKeyboardButton("📝 Грамматика", callback_data="start_grammar")],
        [InlineKeyboardButton("⚙️ Настройки", callback_data="set_menu")],
    ]
    if show_a2_upgrade:
        keyboard.insert(1, [InlineKeyboardButton("🚀 Перейти на A2.1", callback_data="set_lvl_A2_1")])
    error_buttons = []
    if has_word_errors:
        error_buttons.append(InlineKeyboardButton("🔁 Ошибки (слова)", callback_data="fc_errors_start"))
    if has_phrase_errors:
        error_buttons.append(InlineKeyboardButton("🔁 Ошибки (фразы)", callback_data="pf_errors_start"))
    if error_buttons:
        keyboard.insert(1, error_buttons)
    return InlineKeyboardMarkup(keyboard)


async def show_progress(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user's learning progress."""
    user_id = update.effective_user.id
    stats = await get_user_stats(user_id)
    total_vocab = _get_total_vocab()
    streak = await get_user_streak(user_id)
    achievements = await get_user_achievements(user_id)

    has_word_errors = stats.get("words_with_errors", 0) > 0
    has_phrase_errors = stats.get("phrases_with_errors", 0) > 0
    settings = await get_user_settings(user_id)

    total_a1_vocab = _get_total_vocab_for_major("A1")
    a1_pct = (stats["mastered_words"] / total_a1_vocab * 100) if total_a1_vocab > 0 else 0
    has_a2_content = any(lvl["major"] == "A2" and lvl["sub"] == "1" for lvl in get_levels_with_content())
    show_a2_upgrade = settings.get("major_level") == "A1" and a1_pct >= 80 and has_a2_content

    suffix = ""
    if show_a2_upgrade:
        suffix = (
            "\n\n🎓 Вы завершили основную часть A1!\n"
            f"Прогресс A1: {a1_pct:.0f}%.\n"
            "Можно перейти на уровень A2.1."
        )

    text = _build_stats_text(stats, total_vocab, suffix=suffix, streak=streak, achievements=achievements)

    await update.message.reply_text(
        text,
        reply_markup=_build_keyboard(has_word_errors, has_phrase_errors, show_a2_upgrade=show_a2_upgrade)
    )


async def progress_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle progress refresh callback."""
    query = update.callback_query
    await query.answer()

    if query.data == "progress_refresh":
        user_id = update.effective_user.id
        stats = await get_user_stats(user_id)
        total_vocab = _get_total_vocab()
        streak = await get_user_streak(user_id)
        achievements = await get_user_achievements(user_id)

        has_word_errors = stats.get("words_with_errors", 0) > 0
        has_phrase_errors = stats.get("phrases_with_errors", 0) > 0
        settings = await get_user_settings(user_id)
        total_a1_vocab = _get_total_vocab_for_major("A1")
        a1_pct = (stats["mastered_words"] / total_a1_vocab * 100) if total_a1_vocab > 0 else 0
        has_a2_content = any(lvl["major"] == "A2" and lvl["sub"] == "1" for lvl in get_levels_with_content())
        show_a2_upgrade = settings.get("major_level") == "A1" and a1_pct >= 80 and has_a2_content

        suffix = "\n(Обновлено)"
        if show_a2_upgrade:
            suffix += (
                "\n\n🎓 Вы завершили основную часть A1!\n"
                f"Прогресс A1: {a1_pct:.0f}%.\n"
                "Можно перейти на уровень A2.1."
            )

        text = _build_stats_text(stats, total_vocab, suffix=suffix, streak=streak, achievements=achievements)

        await query.edit_message_text(
            text,
            reply_markup=_build_keyboard(has_word_errors, has_phrase_errors, show_a2_upgrade=show_a2_upgrade)
        )
