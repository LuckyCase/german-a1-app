from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ContextTypes
import logging
import aiohttp

from bot.database import get_or_create_user, get_pool
from bot.config import WEB_APP_URL, TELEGRAM_BOT_TOKEN, DATABASE_URL

logger = logging.getLogger(__name__)


async def check_bot_status(context: ContextTypes.DEFAULT_TYPE = None) -> dict:
    """Check bot systems status."""
    status = {
        "webhook": False,
        "database": False,
        "web_app": False,
        "errors": []
    }
    
    # Check Webhook via Telegram API
    if TELEGRAM_BOT_TOKEN:
        try:
            # Try to get webhook info from Telegram API
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getWebhookInfo',
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    if response.status == 200:
                        webhook_info = await response.json()
                        if webhook_info.get('ok'):
                            webhook_url = webhook_info.get('result', {}).get('url', '')
                            if webhook_url:
                                status["webhook"] = True
                            else:
                                status["errors"].append("Webhook не настроен")
                        else:
                            status["errors"].append("Ошибка проверки webhook")
                    else:
                        status["errors"].append("Не удалось проверить webhook")
        except Exception as e:
            logger.error(f"Error checking webhook: {e}")
            status["errors"].append(f"Webhook: {str(e)[:50]}")
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
            logger.error(f"Error checking database: {e}")
            status["errors"].append(f"БД: {str(e)[:50]}")
    else:
        status["errors"].append("DATABASE_URL не настроен")
    
    # Check Web App URL
    if WEB_APP_URL:
        # Try to verify web app is accessible
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    WEB_APP_URL,
                    timeout=aiohttp.ClientTimeout(total=5),
                    allow_redirects=True
                ) as response:
                    if response.status in [200, 301, 302]:
                        status["web_app"] = True
                    else:
                        status["errors"].append(f"Web App недоступен (код {response.status})")
        except Exception as e:
            logger.error(f"Error checking web app: {e}")
            status["errors"].append(f"Web App: {str(e)[:50]}")
    else:
        status["errors"].append("WEB_APP_URL не настроен")
    
    return status


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command - show welcome message, status and Web App button."""
    user = update.effective_user
    
    # Check system status
    status = await check_bot_status(context)
    all_ok = status["webhook"] and status["database"] and status["web_app"]
    
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
        f"Добро пожаловать в бота для изучения немецкого языка уровня A1!\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 **Статус систем:**\n\n"
        f"{status_icons[status['webhook']]} Webhook\n"
        f"{status_icons[status['database']]} База данных\n"
        f"{status_icons[status['web_app']]} Web приложение\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
    )
    
    if all_ok:
        message += (
            "🎉 Все системы работают и подключены!\n\n"
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
