"""Exercises handler — supports multiple_choice, fill_blank, matching, scramble tasks."""
import random
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, ConversationHandler, CommandHandler,
    CallbackQueryHandler, MessageHandler, filters
)

from bot.content_manager import (
    get_exercise_sets, get_exercise_tasks,
    get_current_level, get_levels_with_content
)
from bot.database import save_exercise_set_progress, update_user_activity

logger = logging.getLogger(__name__)

# Conversation states (unique range: 30-33)
EX_LEVEL_SELECT, EX_SET_SELECT, EX_TASK, EX_ANSWER = range(30, 34)

SESSION_PREFIX = "ex_"


def _levenshtein(a: str, b: str) -> int:
    """Compute Levenshtein distance between two strings."""
    if len(a) < len(b):
        return _levenshtein(b, a)
    if len(b) == 0:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a):
        curr = [i + 1]
        for j, cb in enumerate(b):
            curr.append(min(
                prev[j + 1] + 1,
                curr[j] + 1,
                prev[j] + (0 if ca == cb else 1)
            ))
        prev = curr
    return prev[-1]


def _get_ex_level(context) -> tuple:
    return context.user_data.get("ex_level", get_current_level())


async def exercises_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start exercises session — show level selection."""
    context.user_data["ex_level"] = context.user_data.get("user_level", get_current_level())

    levels = get_levels_with_content()
    if len(levels) > 1:
        keyboard = []
        for level in levels:
            keyboard.append([InlineKeyboardButton(
                f"{'✓ ' if level['is_current'] else ''}{level['display_name']}",
                callback_data=f"ex_level_{level['major']}_{level['sub']}"
            )])
        keyboard.append([InlineKeyboardButton("Отмена", callback_data="ex_cancel")])

        text = "Выберите уровень для упражнений:"
        if update.message:
            await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        elif update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        return EX_LEVEL_SELECT
    else:
        return await _show_sets(update, context)


async def ex_level_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle level choice."""
    query = update.callback_query
    await query.answer()

    if query.data == "ex_cancel":
        await query.edit_message_text("Упражнения отменены.")
        return ConversationHandler.END

    parts = query.data.replace("ex_level_", "").split("_")
    if len(parts) == 2:
        context.user_data["ex_level"] = (parts[0], parts[1])

    return await _show_sets(update, context)


async def _show_sets(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show available exercise sets."""
    major, sub = _get_ex_level(context)
    sets = get_exercise_sets(major, sub)

    if not sets:
        text = f"Упражнения для уровня {major}.{sub} не найдены."
        if update.callback_query:
            await update.callback_query.edit_message_text(text)
        elif update.message:
            await update.message.reply_text(text)
        return ConversationHandler.END

    keyboard = []
    for s in sets:
        keyboard.append([InlineKeyboardButton(
            f"{s['name']} ({s['tasks_count']} заданий)",
            callback_data=f"ex_set_{s['id']}"
        )])
    keyboard.append([InlineKeyboardButton("Отмена", callback_data="ex_cancel")])

    text = f"Уровень: {major}.{sub}\n\nВыберите набор упражнений:"
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    elif update.message:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    return EX_SET_SELECT


async def ex_set_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Load tasks and start exercise session."""
    query = update.callback_query
    await query.answer()

    if query.data == "ex_cancel":
        await query.edit_message_text("Упражнения отменены.")
        return ConversationHandler.END

    set_id = query.data.replace("ex_set_", "")
    major, sub = _get_ex_level(context)

    tasks = get_exercise_tasks(set_id, major, sub)
    if not tasks:
        await query.edit_message_text("Задания не найдены.")
        return ConversationHandler.END

    # Track activity for streak
    user_id = update.effective_user.id
    await update_user_activity(user_id)

    random.shuffle(tasks)

    context.user_data["ex_set_id"] = set_id
    context.user_data["ex_tasks"] = tasks
    context.user_data["ex_index"] = 0
    context.user_data["ex_correct"] = 0
    context.user_data["ex_total"] = len(tasks)

    await query.edit_message_text(
        f"Упражнение: {set_id}\n"
        f"Заданий: {len(tasks)}\n\n"
        f"Готовы?",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Начать!", callback_data="ex_next")]
        ])
    )
    return EX_TASK


async def show_next_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Route to the correct task renderer."""
    query = update.callback_query
    await query.answer()

    tasks = context.user_data.get("ex_tasks", [])
    index = context.user_data.get("ex_index", 0)

    if index >= len(tasks):
        return await _show_results(query, context)

    task = tasks[index]
    task_type = task.get("type", "multiple_choice")
    total = len(tasks)

    if task_type == "fill_blank":
        return await _show_fill_blank(query, context, task, index, total)
    elif task_type == "matching":
        return await _show_matching(query, context, task, index, total)
    elif task_type == "scramble":
        return await _show_scramble(query, context, task, index, total)
    else:
        return await _show_multiple_choice(query, context, task, index, total)


async def _show_multiple_choice(query, context, task, index, total):
    """Render multiple_choice task."""
    options = task.get("options", [])
    keyboard = []
    for i, opt in enumerate(options):
        keyboard.append([InlineKeyboardButton(opt, callback_data=f"ex_ans_{i}")])

    context.user_data["ex_current_task"] = task
    context.user_data["ex_task_type"] = "multiple_choice"

    await query.edit_message_text(
        f"Задание {index + 1} из {total}\n\n"
        f"{task.get('question', '')}",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return EX_ANSWER


async def _show_fill_blank(query, context, task, index, total):
    """Render fill_blank task — user types the answer."""
    sentence = task.get("sentence", "")
    hint = task.get("hint", "")

    context.user_data["ex_current_task"] = task
    context.user_data["ex_task_type"] = "fill_blank"

    hint_line = f"\nПодсказка: {hint}" if hint else ""

    await query.edit_message_text(
        f"Задание {index + 1} из {total}\n\n"
        f"Заполните пропуск:\n{sentence}{hint_line}\n\n"
        f"Напишите ответ в чат:"
    )
    return EX_ANSWER


async def _show_matching(query, context, task, index, total):
    """Render matching task — sequential pair matching."""
    pairs = task.get("pairs", [])
    if not pairs:
        context.user_data["ex_index"] = index + 1
        return await show_next_task(type("Q", (), {"callback_query": query})(), context)

    # Shuffle right side
    right_options = [p["right"] for p in pairs]
    random.shuffle(right_options)

    context.user_data["ex_current_task"] = task
    context.user_data["ex_task_type"] = "matching"
    context.user_data["ex_match_index"] = 0
    context.user_data["ex_match_right"] = right_options
    context.user_data["ex_match_correct"] = 0

    return await _show_match_step(query, context, pairs, right_options, 0, index, total)


async def _show_match_step(query, context, pairs, right_options, match_idx, task_idx, total):
    """Show one step of matching."""
    left = pairs[match_idx]["left"]
    keyboard = []
    for i, opt in enumerate(right_options):
        keyboard.append([InlineKeyboardButton(opt, callback_data=f"ex_match_{i}")])

    await query.edit_message_text(
        f"Задание {task_idx + 1} из {total} | Пара {match_idx + 1}/{len(pairs)}\n\n"
        f"Найдите пару для:\n{left}",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return EX_ANSWER


async def _show_scramble(query, context, task, index, total):
    """Render scramble task — tap words in order."""
    words = task.get("words", [])
    if not words:
        context.user_data["ex_index"] = index + 1
        return await show_next_task(type("Q", (), {"callback_query": query})(), context)

    shuffled = list(range(len(words)))
    random.shuffle(shuffled)

    context.user_data["ex_current_task"] = task
    context.user_data["ex_task_type"] = "scramble"
    context.user_data["ex_scramble_order"] = shuffled
    context.user_data["ex_scramble_selected"] = []

    return await _show_scramble_step(query, context, task, shuffled, [], index, total)


async def _show_scramble_step(query, context, task, shuffled, selected, task_idx, total):
    """Show scramble step with remaining words."""
    words = task.get("words", [])
    translation = task.get("translation", "")

    built = " ".join(words[i] for i in selected)
    keyboard = []
    for idx in shuffled:
        if idx not in selected:
            keyboard.append([InlineKeyboardButton(words[idx], callback_data=f"ex_scr_{idx}")])

    text = (
        f"Задание {task_idx + 1} из {total}\n\n"
        f"Составьте предложение:\n"
    )
    if translation:
        text += f"({translation})\n"
    if built:
        text += f"\nТекущий вариант: {built}\n"
    text += "\nВыберите следующее слово:"

    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    return EX_ANSWER


async def handle_exercise_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle answer for multiple_choice and matching (callback-based)."""
    query = update.callback_query
    await query.answer()

    task_type = context.user_data.get("ex_task_type", "multiple_choice")
    task = context.user_data.get("ex_current_task", {})

    if task_type == "matching":
        return await _handle_matching_answer(query, context)
    elif task_type == "scramble":
        return await _handle_scramble_answer(query, context)

    # multiple_choice
    answer_index = int(query.data.replace("ex_ans_", ""))
    correct_index = task.get("correct", 0)
    is_correct = answer_index == correct_index

    if is_correct:
        context.user_data["ex_correct"] = context.user_data.get("ex_correct", 0) + 1
        result = "Правильно!"
    else:
        options = task.get("options", [])
        correct_text = options[correct_index] if correct_index < len(options) else "?"
        result = f"Неправильно! Ответ: {correct_text}"

    explanation = task.get("explanation", "")
    exp_line = f"\n{explanation}" if explanation else ""

    context.user_data["ex_index"] = context.user_data.get("ex_index", 0) + 1

    await query.edit_message_text(
        f"{result}{exp_line}",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Далее", callback_data="ex_next")]
        ])
    )
    return EX_TASK


async def handle_fill_blank_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text input for fill_blank tasks."""
    task_type = context.user_data.get("ex_task_type")
    if task_type != "fill_blank":
        return EX_ANSWER

    task = context.user_data.get("ex_current_task", {})
    correct_answer = task.get("answer", "")
    user_answer = update.message.text.strip()

    distance = _levenshtein(user_answer.lower(), correct_answer.lower())
    is_correct = distance <= 1

    if is_correct:
        context.user_data["ex_correct"] = context.user_data.get("ex_correct", 0) + 1
        if distance == 0:
            result = "Правильно!"
        else:
            result = f"Почти правильно! (принято)\nТочный ответ: {correct_answer}"
    else:
        result = f"Неправильно!\nПравильный ответ: {correct_answer}"

    explanation = task.get("explanation", "")
    exp_line = f"\n{explanation}" if explanation else ""

    context.user_data["ex_index"] = context.user_data.get("ex_index", 0) + 1

    await update.message.reply_text(
        f"{result}{exp_line}",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Далее", callback_data="ex_next")]
        ])
    )
    return EX_TASK


async def _handle_matching_answer(query, context):
    """Handle one step of matching."""
    task = context.user_data.get("ex_current_task", {})
    pairs = task.get("pairs", [])
    match_idx = context.user_data.get("ex_match_index", 0)
    right_options = context.user_data.get("ex_match_right", [])

    selected_idx = int(query.data.replace("ex_match_", ""))
    selected_text = right_options[selected_idx] if selected_idx < len(right_options) else ""
    correct_text = pairs[match_idx]["right"]

    is_correct = selected_text == correct_text
    if is_correct:
        context.user_data["ex_match_correct"] = context.user_data.get("ex_match_correct", 0) + 1

    match_idx += 1
    context.user_data["ex_match_index"] = match_idx

    if match_idx >= len(pairs):
        # All pairs done
        match_correct = context.user_data.get("ex_match_correct", 0)
        if match_correct == len(pairs):
            context.user_data["ex_correct"] = context.user_data.get("ex_correct", 0) + 1

        result = f"{'Верно!' if is_correct else f'Неверно! Ответ: {correct_text}'}\n\n"
        result += f"Соединение пар завершено: {match_correct}/{len(pairs)}"

        context.user_data["ex_index"] = context.user_data.get("ex_index", 0) + 1

        await query.edit_message_text(
            result,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Далее", callback_data="ex_next")]
            ])
        )
        return EX_TASK
    else:
        # Show result and next pair
        tasks = context.user_data.get("ex_tasks", [])
        task_idx = context.user_data.get("ex_index", 0)
        total = len(tasks)

        result_text = "Верно! " if is_correct else f"Неверно! ({correct_text}). "
        await query.edit_message_text(result_text + "Следующая пара...")

        # Remove selected option
        right_options = [opt for i, opt in enumerate(right_options) if i != selected_idx]
        context.user_data["ex_match_right"] = right_options

        return await _show_match_step(query, context, pairs, right_options, match_idx, task_idx, total)


async def _handle_scramble_answer(query, context):
    """Handle one word tap in scramble."""
    task = context.user_data.get("ex_current_task", {})
    words = task.get("words", [])
    selected = context.user_data.get("ex_scramble_selected", [])
    shuffled = context.user_data.get("ex_scramble_order", [])

    word_idx = int(query.data.replace("ex_scr_", ""))
    selected.append(word_idx)
    context.user_data["ex_scramble_selected"] = selected

    if len(selected) >= len(words):
        # All words selected — check order
        built = " ".join(words[i] for i in selected)
        correct = task.get("answer", " ".join(words))
        is_correct = built.lower() == correct.lower()

        if is_correct:
            context.user_data["ex_correct"] = context.user_data.get("ex_correct", 0) + 1
            result = f"Правильно!\n{built}"
        else:
            result = f"Неправильно!\nВаш вариант: {built}\nПравильно: {correct}"

        explanation = task.get("explanation", "")
        if explanation:
            result += f"\n{explanation}"

        context.user_data["ex_index"] = context.user_data.get("ex_index", 0) + 1

        await query.edit_message_text(
            result,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Далее", callback_data="ex_next")]
            ])
        )
        return EX_TASK
    else:
        tasks = context.user_data.get("ex_tasks", [])
        task_idx = context.user_data.get("ex_index", 0)
        total = len(tasks)
        return await _show_scramble_step(query, context, task, shuffled, selected, task_idx, total)


async def _show_results(query, context):
    """Show final results and save progress."""
    correct = context.user_data.get("ex_correct", 0)
    total = context.user_data.get("ex_total", 0)
    set_id = context.user_data.get("ex_set_id", "")
    major, sub = _get_ex_level(context)
    user_id = query.from_user.id

    percentage = (correct / total * 100) if total > 0 else 0

    await save_exercise_set_progress(user_id, set_id, major, sub, total, correct)

    await query.edit_message_text(
        f"Упражнение завершено!\n\n"
        f"Правильно: {correct} из {total}\n"
        f"Результат: {percentage:.0f}%\n\n"
        f"Используйте /exercises для новых упражнений."
    )
    return ConversationHandler.END


async def cancel_exercises(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel exercises session."""
    if update.message:
        await update.message.reply_text("Упражнения отменены.")
    return ConversationHandler.END


def get_exercises_handler():
    """Build ConversationHandler for exercises."""
    return ConversationHandler(
        entry_points=[
            CommandHandler("exercises", exercises_start),
            CallbackQueryHandler(exercises_start, pattern="^start_exercises$"),
        ],
        states={
            EX_LEVEL_SELECT: [
                CallbackQueryHandler(ex_level_selected, pattern="^ex_level_"),
                CallbackQueryHandler(ex_level_selected, pattern="^ex_cancel$"),
            ],
            EX_SET_SELECT: [
                CallbackQueryHandler(ex_set_selected, pattern="^ex_set_"),
                CallbackQueryHandler(ex_set_selected, pattern="^ex_cancel$"),
            ],
            EX_TASK: [
                CallbackQueryHandler(show_next_task, pattern="^ex_next$"),
            ],
            EX_ANSWER: [
                CallbackQueryHandler(handle_exercise_answer, pattern="^ex_ans_"),
                CallbackQueryHandler(handle_exercise_answer, pattern="^ex_match_"),
                CallbackQueryHandler(handle_exercise_answer, pattern="^ex_scr_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_fill_blank_text),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_exercises)],
        per_message=False,
        per_chat=True,
        per_user=True,
    )
