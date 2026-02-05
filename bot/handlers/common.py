from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ContextTypes
import logging

from bot.database import get_or_create_user, get_pool
from bot.config import WEB_APP_URL, TELEGRAM_BOT_TOKEN, DATABASE_URL

logger = logging.getLogger(__name__)


async def check_bot_status() -> dict:
    """Check bot systems status."""
    status = {
        "telegram": False,
        "database": False,
        "web_app": False,
        "errors": []
    }
    
    # Check Telegram token
    if TELEGRAM_BOT_TOKEN:
        status["telegram"] = True
    else:
        status["errors"].append("Telegram токен не настроен")
    
    # Check Database
    if DATABASE_URL:
        try:
            pool = await get_pool()
            async with pool.acquire() as conn:
                await conn.fetchval('SELECT 1')
            status["database"] = True
        except Exception as e:
            status["errors"].append(f"БД: {str(e)[:50]}")
    else:
        status["errors"].append("DATABASE_URL не настроен")
    
    # Check Web App URL
    if WEB_APP_URL:
        status["web_app"] = True
    else:
        status["errors"].append("WEB_APP_URL не настроен")
    
    return status


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command - show status and Web App button."""
    user = update.effective_user
    
    # Check system status
    status = await check_bot_status()
    all_ok = status["telegram"] and status["database"] and status["web_app"]
    
    # Try to register user if database is working
    if status["database"]:
        try:
            await get_or_create_user(user.id, user.username, user.first_name)
        except Exception as e:
            logger.error(f"Failed to register user: {e}")
    
    # Build status message
    status_icons = {
        True: "✅",
        False: "❌"
    }
    
    message = (
        f"Hallo, {user.first_name}! 👋\n\n"
        f"🇩🇪 **German A1 Learning Bot**\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 **Статус систем:**\n\n"
        f"{status_icons[status['telegram']]} Telegram API\n"
        f"{status_icons[status['database']]} База данных\n"
        f"{status_icons[status['web_app']]} Web приложение\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
    )
    
    if all_ok:
        message += (
            "🎉 Все системы работают!\n\n"
            "Нажмите кнопку ниже, чтобы открыть приложение для изучения немецкого языка."
        )
        
        keyboard = [[
            InlineKeyboardButton(
                "🚀 Открыть приложение", 
                web_app=WebAppInfo(url=WEB_APP_URL)
            )
        ]]
        
        await update.message.reply_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
    else:
        message += (
            "⚠️ Обнаружены проблемы:\n\n"
        )
        for error in status["errors"]:
            message += f"• {error}\n"
        
        message += "\nПопробуйте позже или обратитесь к администратору."
        
        await update.message.reply_text(message, parse_mode="Markdown")
