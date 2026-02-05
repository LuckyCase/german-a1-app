import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Database URL (PostgreSQL for production, SQLite fallback for local dev)
DATABASE_URL = os.getenv("DATABASE_URL")

# Default reminder time (UTC)
DEFAULT_REMINDER_HOUR = 9
DEFAULT_REMINDER_MINUTE = 0

# Web App URL (same as bot URL since they run on same service)
WEB_APP_URL = os.getenv("WEB_APP_URL", "https://german-a1-bot.onrender.com")
