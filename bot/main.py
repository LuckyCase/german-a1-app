import asyncio
import logging
from telegram.ext import Application, CommandHandler, MessageHandler, filters

from bot.config import TELEGRAM_BOT_TOKEN
from bot.database import init_db
from bot.content_manager import init_content
from bot.handlers.common import start, redirect_commands_to_webapp
from bot.handlers.reminders import setup_reminder_job
from bot.handlers.admin import broadcast_command, send_command
from bot.monitoring import init_sentry, telegram_error_handler_factory

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def main():
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not set!")
        return

    init_sentry()
    asyncio.run(init_db())
    init_content()

    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("broadcast", broadcast_command))
    application.add_handler(CommandHandler("send", send_command))
    application.add_handler(MessageHandler(filters.COMMAND, redirect_commands_to_webapp))

    setup_reminder_job(application)
    application.add_error_handler(telegram_error_handler_factory())

    logger.info("Starting bot (Web App entry only)...")
    application.run_polling(allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    main()
