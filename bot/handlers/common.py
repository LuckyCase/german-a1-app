from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from bot.database import get_or_create_user
from bot.data.vocabulary import get_categories
from bot.data.grammar import get_all_tests


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    user = update.effective_user
    await get_or_create_user(user.id, user.username, user.first_name)

    welcome_message = (
        f"Hallo, {user.first_name}! 👋\n\n"
        f"Добро пожаловать в бот для изучения немецкого языка уровня A1! 🇩🇪\n\n"
        f"Этот бот поможет вам подготовиться к экзамену Goethe-Zertifikat A1.\n\n"
        f"📚 Что я умею:\n"
        f"• Карточки со словами (flashcards)\n"
        f"• Тесты по грамматике\n"
        f"• Аудио произношение\n"
        f"• Отслеживание прогресса\n"
        f"• Ежедневные напоминания\n\n"
        f"🎯 Команды:\n"
        f"/flashcards - учить слова\n"
        f"/grammar - грамматические тесты\n"
        f"/progress - ваш прогресс\n"
        f"/reminder - настроить напоминания\n"
        f"/audio <текст> - прослушать произношение\n"
        f"/help - справка\n\n"
        f"Viel Erfolg! Удачи в изучении! 🍀"
    )

    keyboard = [
        [
            InlineKeyboardButton("📚 Учить слова", callback_data="menu_flashcards"),
            InlineKeyboardButton("📝 Грамматика", callback_data="menu_grammar")
        ],
        [
            InlineKeyboardButton("📊 Прогресс", callback_data="menu_progress"),
            InlineKeyboardButton("⏰ Напоминания", callback_data="menu_reminder")
        ]
    ]

    await update.message.reply_text(
        welcome_message,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command."""
    categories = get_categories()
    tests = get_all_tests()

    help_text = (
        "📖 Справка по боту\n"
        "═══════════════════\n\n"
        "🎯 Основные команды:\n\n"
        "/start - главное меню\n"
        "/flashcards - изучение слов с карточками\n"
        "/grammar - грамматические тесты\n"
        "/progress - ваша статистика\n"
        "/reminder - настройка напоминаний\n"
        "/audio <текст> - произношение текста\n"
        "/help - эта справка\n\n"
        f"📚 Категории слов ({sum(c['count'] for c in categories)} слов):\n"
    )

    for cat in categories:
        help_text += f"  • {cat['name']} ({cat['count']})\n"

    help_text += f"\n📝 Грамматические тесты ({len(tests)}):\n"

    for test in tests:
        help_text += f"  • {test['name']}\n"

    help_text += (
        "\n💡 Советы:\n"
        "• Занимайтесь каждый день по 15-20 минут\n"
        "• Учите слова с артиклями (der, die, das)\n"
        "• Используйте аудио для улучшения произношения\n"
        "• Повторяйте сложные слова чаще\n\n"
        "Viel Erfolg! 🇩🇪"
    )

    await update.message.reply_text(help_text)


async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle menu button callbacks."""
    query = update.callback_query
    await query.answer()

    if query.data == "menu_flashcards":
        await query.edit_message_text(
            "📚 Изучение слов\n\n"
            "Используйте команду /flashcards чтобы начать сессию изучения слов.\n\n"
            "Вы увидите немецкое слово и должны выбрать правильный перевод из вариантов."
        )
    elif query.data == "menu_grammar":
        await query.edit_message_text(
            "📝 Грамматика\n\n"
            "Используйте команду /grammar чтобы пройти грамматический тест.\n\n"
            "Доступны тесты по артиклям, глаголам, падежам и другим темам A1."
        )
    elif query.data == "menu_progress":
        await query.edit_message_text(
            "📊 Прогресс\n\n"
            "Используйте команду /progress чтобы посмотреть вашу статистику изучения."
        )
    elif query.data == "menu_reminder":
        await query.edit_message_text(
            "⏰ Напоминания\n\n"
            "Используйте команду /reminder чтобы настроить ежедневные напоминания."
        )
