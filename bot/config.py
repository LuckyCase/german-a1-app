import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Database path
DATABASE_PATH = os.getenv("DATABASE_PATH", "data/bot.db")

# Default reminder time (UTC)
DEFAULT_REMINDER_HOUR = 9
DEFAULT_REMINDER_MINUTE = 0
