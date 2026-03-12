import asyncio
import logging
from telegram.ext import Application, CommandHandler, CallbackQueryHandler

from bot.config import TELEGRAM_BOT_TOKEN
from bot.database import init_db
from bot.content_manager import init_content
from bot.handlers.common import start, help_command
from bot.handlers.flashcards import get_flashcards_handler
from bot.handlers.grammar import get_grammar_handler
from bot.handlers.phrases_flashcards import get_phrases_flashcards_handler
from bot.handlers.progress import show_progress, progress_callback
from bot.handlers.reminders import reminder_settings, reminder_callback, setup_reminder_job
from bot.handlers.audio import audio_command
from bot.handlers.feedback import get_feedback_handler, feedback_callback
from bot.handlers.settings import show_settings, settings_callback
from bot.handlers.admin import broadcast_command, send_command
from bot.handlers.exercises import get_exercises_handler
from bot.handlers.diagnostic import get_diagnostic_handler
from bot.monitoring import init_sentry, telegram_error_handler_factory

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

    init_sentry()

    # Initialize database
    asyncio.run(init_db())
    
    # Initialize content from JSON files
    init_content()

    # Create application
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("progress", show_progress))
    application.add_handler(CommandHandler("reminder", reminder_settings))
    application.add_handler(CommandHandler("audio", audio_command))
    application.add_handler(CommandHandler("settings", show_settings))
    application.add_handler(CommandHandler("broadcast", broadcast_command))
    application.add_handler(CommandHandler("send", send_command))

    # Add callback handlers BEFORE conversation handlers (order matters!)
    # These must be registered first to catch callbacks when no conversation is active
    application.add_handler(CallbackQueryHandler(progress_callback, pattern="^progress_refresh$"))
    application.add_handler(CallbackQueryHandler(settings_callback, pattern="^set_"))
    application.add_handler(CallbackQueryHandler(reminder_callback, pattern="^rem_"))
    application.add_handler(CallbackQueryHandler(feedback_callback, pattern="^feedback_back$"))

    # Add conversation handlers (these should come after regular callback handlers)
    # fc_errors_start and pf_errors_start are entry_points inside these handlers
    application.add_handler(get_diagnostic_handler())
    application.add_handler(get_flashcards_handler())
    application.add_handler(get_phrases_flashcards_handler())
    application.add_handler(get_grammar_handler())
    application.add_handler(get_exercises_handler())
    application.add_handler(get_feedback_handler())

    # Error handler (Sentry + Telegram admin notifications)
    application.add_error_handler(telegram_error_handler_factory())

    # Setup reminder job
    setup_reminder_job(application)

    # Start the bot
    logger.info("Starting bot...")
    application.run_polling(allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    main()
