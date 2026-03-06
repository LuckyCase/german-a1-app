import asyncio
import logging
from telegram import Update
from telegram.ext import ContextTypes

from bot.config import ADMIN_IDS
from bot.database import get_all_user_ids

logger = logging.getLogger(__name__)


def _is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/broadcast <text> — send a message to all users (admin only)."""
    if not _is_admin(update.effective_user.id):
        return

    text = " ".join(context.args).strip() if context.args else ""
    if not text:
        await update.message.reply_text("Использование: /broadcast <текст>")
        return

    user_ids = await get_all_user_ids()
    total = len(user_ids)
    status_msg = await update.message.reply_text(f"Отправляю {total} пользователям...")

    sent, failed = 0, 0
    for uid in user_ids:
        try:
            await context.bot.send_message(chat_id=uid, text=text)
            sent += 1
            await asyncio.sleep(0.05)  # ~20 msg/sec, Telegram limit 30/sec
        except Exception as e:
            logger.warning(f"Broadcast failed for {uid}: {e}")
            failed += 1

    await status_msg.edit_text(
        f"Рассылка завершена.\n✅ Доставлено: {sent}\n❌ Ошибок: {failed}"
    )


async def send_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/send <user_id> <text> — send a message to a specific user (admin only)."""
    if not _is_admin(update.effective_user.id):
        return

    if not context.args or len(context.args) < 2:
        await update.message.reply_text("Использование: /send <user_id> <текст>")
        return

    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("user_id должен быть числом.")
        return

    text = " ".join(context.args[1:])
    try:
        await context.bot.send_message(chat_id=target_id, text=text)
        await update.message.reply_text(f"✅ Сообщение отправлено пользователю {target_id}.")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")
