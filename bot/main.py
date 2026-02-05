import asyncio
import logging
from telegram.ext import Application, CommandHandler, CallbackQueryHandler

from bot.config import TELEGRAM_BOT_TOKEN
from bot.database import init_db
from bot.handlers.common import start, help_command, menu_callback
from bot.handlers.flashcards import get_flashcards_handler
from bot.handlers.grammar import get_grammar_handler
from bot.handlers.progress import show_progress, progress_callback
from bot.handlers.reminders import reminder_settings, reminder_callback, setup_reminder_job
from bot.handlers.audio import audio_command

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


def main():
    """Start the bot."""
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not set!")
        return

    # Initialize database
    asyncio.run(init_db())

    # Create application
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("progress", show_progress))
    application.add_handler(CommandHandler("reminder", reminder_settings))
    application.add_handler(CommandHandler("audio", audio_command))

    # Add callback handlers BEFORE conversation handlers (order matters!)
    # These must be registered first to catch callbacks when no conversation is active
    application.add_handler(CallbackQueryHandler(menu_callback, pattern="^menu_"))
    application.add_handler(CallbackQueryHandler(progress_callback, pattern="^(progress_|start_flashcards|start_grammar)"))
    application.add_handler(CallbackQueryHandler(reminder_callback, pattern="^rem_"))

    # Add conversation handlers (these should come after regular callback handlers)
    application.add_handler(get_flashcards_handler())
    application.add_handler(get_grammar_handler())

    # Setup reminder job
    setup_reminder_job(application)

    # Start the bot
    logger.info("Starting bot...")
    application.run_polling(allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    main()
