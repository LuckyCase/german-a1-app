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

# Admin user IDs (comma-separated in env, e.g. "123456,789012")
ADMIN_IDS = [
    int(x.strip())
    for x in os.getenv("ADMIN_IDS", "").split(",")
    if x.strip().isdigit()
]

# Sentry DSN (optional — leave empty to disable)
SENTRY_DSN = os.getenv("SENTRY_DSN", "")

# Admin secret for web admin panel (Bearer token)
ADMIN_SECRET = os.getenv("ADMIN_SECRET", "")

# Pronunciation check (hybrid STT)
PRONUN_LOCAL_ENABLED = os.getenv("PRONUN_LOCAL_ENABLED", "1") == "1"
PRONUN_CLOUD_ENABLED = os.getenv("PRONUN_CLOUD_ENABLED", "0") == "1"
PRONUN_CLOUD_PROVIDER = os.getenv("PRONUN_CLOUD_PROVIDER", "openai")
PRONUN_CLOUD_API_KEY = os.getenv("PRONUN_CLOUD_API_KEY", "")
PRONUN_MIN_CONFIDENCE = float(os.getenv("PRONUN_MIN_CONFIDENCE", "0.65"))
PRONUN_TIMEOUT_SEC = int(os.getenv("PRONUN_TIMEOUT_SEC", "12"))
PRONUN_MAX_AUDIO_BYTES = int(os.getenv("PRONUN_MAX_AUDIO_BYTES", str(2 * 1024 * 1024)))
PRONUN_MIN_AUDIO_BYTES = int(os.getenv("PRONUN_MIN_AUDIO_BYTES", "4000"))
PRONUN_RATE_LIMIT_PER_HOUR = int(os.getenv("PRONUN_RATE_LIMIT_PER_HOUR", "60"))
PRONUN_VOSK_MODEL_PATH = os.getenv("PRONUN_VOSK_MODEL_PATH", "")
