import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, CallbackQueryHandler

from bot.data.grammar import get_all_tests, get_test, get_test_questions
from bot.database import save_grammar_result, update_daily_stats

# Conversation states
TEST_SELECT, QUESTION, RESULT = range(3)


async def grammar_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start grammar test selection."""
    tests = get_all_tests()

    keyboard = []
    for test in tests:
        keyboard.append([
            InlineKeyboardButton(
                f"{test['name']} ({test['questions_count']} вопросов)",
                callback_data=f"gr_test_{test['id']}"
            )
        ])
    keyboard.append([InlineKeyboardButton("Случайный тест", callback_data="gr_test_random")])
    keyboard.append([InlineKeyboardButton("Отмена", callback_data="gr_cancel")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "Выберите грамматический тест:\n\n"
        "Каждый тест проверяет определённую тему грамматики уровня A1.",
        reply_markup=reply_markup
    )
    return TEST_SELECT


async def test_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle test selection."""
    query = update.callback_query
    await query.answer()

    if query.data == "gr_cancel":
        await query.edit_message_text("Тестирование отменено. Используйте /grammar чтобы начать снова.")
        return ConversationHandler.END

    test_id = query.data.replace("gr_test_", "")

    if test_id == "random":
        tests = get_all_tests()
        test_id = random.choice(tests)["id"]

    test = get_test(test_id)
    if not test:
        await query.edit_message_text("Тест не найден. Попробуйте снова.")
        return ConversationHandler.END

    questions = get_test_questions(test_id)
    random.shuffle(questions)

    context.user_data["gr_test_id"] = test_id
    context.user_data["gr_test_name"] = test["name"]
    context.user_data["gr_questions"] = questions
    context.user_data["gr_index"] = 0
    context.user_data["gr_score"] = 0
    context.user_data["gr_answers"] = []

    await query.edit_message_text(
        f"Тест: {test['name']}\n"
        f"{test['description']}\n\n"
        f"Вопросов: {len(questions)}\n\n"
        f"Нажмите кнопку, чтобы начать!",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Начать тест", callback_data="gr_next")]
        ])
    )
    return QUESTION


async def show_next_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show the next question."""
    query = update.callback_query
    await query.answer()

    questions = context.user_data.get("gr_questions", [])
    index = context.user_data.get("gr_index", 0)

    if index >= len(questions):
        # Test complete
        return await show_results(update, context)

    question = questions[index]
    context.user_data["gr_current_question"] = question

    keyboard = []
    for i, option in enumerate(question["options"]):
        keyboard.append([
            InlineKeyboardButton(option, callback_data=f"gr_ans_{i}")
        ])

    await query.edit_message_text(
        f"Вопрос {index + 1} из {len(questions)}\n\n"
        f"{question['question']}",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return QUESTION


async def handle_grammar_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle answer to grammar question."""
    query = update.callback_query
    await query.answer()

    answer_index = int(query.data.replace("gr_ans_", ""))
    question = context.user_data.get("gr_current_question", {})
    correct_index = question.get("correct", 0)

    is_correct = answer_index == correct_index

    if is_correct:
        context.user_data["gr_score"] = context.user_data.get("gr_score", 0) + 1
        result_emoji = "✅"
    else:
        result_emoji = "❌"

    # Store answer for review
    context.user_data["gr_answers"].append({
        "question": question["question"],
        "user_answer": question["options"][answer_index],
        "correct_answer": question["options"][correct_index],
        "is_correct": is_correct,
        "explanation": question.get("explanation", "")
    })

    context.user_data["gr_index"] = context.user_data.get("gr_index", 0) + 1

    await query.edit_message_text(
        f"{result_emoji} {'Правильно!' if is_correct else 'Неправильно!'}\n\n"
        f"Вопрос: {question['question']}\n"
        f"Правильный ответ: {question['options'][correct_index]}\n\n"
        f"{question.get('explanation', '')}",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Следующий вопрос", callback_data="gr_next")]
        ])
    )
    return QUESTION


async def show_results(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show test results."""
    query = update.callback_query

    test_id = context.user_data.get("gr_test_id", "")
    test_name = context.user_data.get("gr_test_name", "")
    score = context.user_data.get("gr_score", 0)
    questions = context.user_data.get("gr_questions", [])
    total = len(questions)
    user_id = update.effective_user.id

    percentage = (score / total * 100) if total > 0 else 0

    # Save result to database
    await save_grammar_result(user_id, test_id, score, total)
    await update_daily_stats(user_id, tests=1, correct=score, total=total)

    # Determine grade
    if percentage >= 90:
        grade = "Отлично! 🌟"
    elif percentage >= 70:
        grade = "Хорошо! 👍"
    elif percentage >= 50:
        grade = "Удовлетворительно 📚"
    else:
        grade = "Нужно повторить материал 📖"

    await query.edit_message_text(
        f"Тест завершён: {test_name}\n\n"
        f"Результат: {score} из {total}\n"
        f"Процент: {percentage:.0f}%\n"
        f"Оценка: {grade}\n\n"
        f"Используйте /grammar чтобы пройти другой тест.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Посмотреть ошибки", callback_data="gr_review")],
            [InlineKeyboardButton("Новый тест", callback_data="gr_new")]
        ])
    )
    return RESULT


async def review_errors(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show review of wrong answers."""
    query = update.callback_query
    await query.answer()

    answers = context.user_data.get("gr_answers", [])
    wrong_answers = [a for a in answers if not a["is_correct"]]

    if not wrong_answers:
        await query.edit_message_text(
            "Поздравляем! Вы ответили на все вопросы правильно! 🎉\n\n"
            "Используйте /grammar чтобы пройти другой тест."
        )
        return ConversationHandler.END

    review_text = "Разбор ошибок:\n\n"
    for i, ans in enumerate(wrong_answers, 1):
        review_text += f"{i}. {ans['question']}\n"
        review_text += f"   Ваш ответ: {ans['user_answer']}\n"
        review_text += f"   Правильно: {ans['correct_answer']}\n"
        review_text += f"   {ans['explanation']}\n\n"

    # Split if too long
    if len(review_text) > 4000:
        review_text = review_text[:4000] + "..."

    await query.edit_message_text(review_text)
    return ConversationHandler.END


async def start_new_test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start a new grammar test."""
    query = update.callback_query
    await query.answer()

    # Clear previous test data
    context.user_data.pop("gr_test_id", None)
    context.user_data.pop("gr_questions", None)
    context.user_data.pop("gr_index", None)
    context.user_data.pop("gr_score", None)
    context.user_data.pop("gr_answers", None)

    tests = get_all_tests()

    keyboard = []
    for test in tests:
        keyboard.append([
            InlineKeyboardButton(
                f"{test['name']} ({test['questions_count']} вопросов)",
                callback_data=f"gr_test_{test['id']}"
            )
        ])
    keyboard.append([InlineKeyboardButton("Случайный тест", callback_data="gr_test_random")])
    keyboard.append([InlineKeyboardButton("Отмена", callback_data="gr_cancel")])

    await query.edit_message_text(
        "Выберите грамматический тест:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return TEST_SELECT


async def cancel_grammar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel grammar test."""
    await update.message.reply_text("Тестирование отменено.")
    return ConversationHandler.END


def get_grammar_handler():
    """Get the ConversationHandler for grammar tests."""
    return ConversationHandler(
        entry_points=[CommandHandler("grammar", grammar_start)],
        states={
            TEST_SELECT: [
                CallbackQueryHandler(test_selected, pattern="^gr_test_"),
                CallbackQueryHandler(test_selected, pattern="^gr_cancel$")
            ],
            QUESTION: [
                CallbackQueryHandler(show_next_question, pattern="^gr_next$"),
                CallbackQueryHandler(handle_grammar_answer, pattern="^gr_ans_")
            ],
            RESULT: [
                CallbackQueryHandler(review_errors, pattern="^gr_review$"),
                CallbackQueryHandler(start_new_test, pattern="^gr_new$")
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel_grammar)],
        per_message=False
    )
