from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters
)
import logging
from datetime import datetime

from bot.database import (
    save_feedback,
    get_user_feedback,
    get_feedback_count,
    FEEDBACK_STATUS_LABELS,
    MAX_FEEDBACK_LENGTH
)

logger = logging.getLogger(__name__)

# Conversation states
WAITING_FOR_FEEDBACK = 1


def format_feedback_date(dt) -> str:
    """Format datetime for display."""
    if isinstance(dt, datetime):
        return dt.strftime("%d.%m.%Y %H:%M")
    return str(dt)


def get_status_label(status: int) -> str:
    """Get status label by code."""
    return FEEDBACK_STATUS_LABELS.get(status, f"❓ Статус {status}")


async def show_feedback_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show feedback menu with user's previous submissions."""
    user_id = update.effective_user.id
    
    # Get user's feedback
    feedback_list = await get_user_feedback(user_id, limit=5)
    total_count = await get_feedback_count(user_id)
    
    message = (
        "💬 **Отзывы и предложения**\n\n"
        "Здесь вы можете оставить отзыв о боте или предложить улучшение. "
        "Мы ценим вашу обратную связь!\n\n"
    )
    
    if feedback_list:
        message += f"📋 **Ваши отзывы** (показаны последние {len(feedback_list)} из {total_count}):\n\n"
        
        for fb in feedback_list:
            # Truncate text for preview
            preview_text = fb["text"][:50] + "..." if len(fb["text"]) > 50 else fb["text"]
            status_label = get_status_label(fb["status"])
            date_str = format_feedback_date(fb["created_at"])
            
            message += f"• {preview_text}\n"
            message += f"  {status_label} | {date_str}\n\n"
    else:
        message += "📭 У вас пока нет отзывов.\n\n"
    
    message += f"📝 Ограничение: {MAX_FEEDBACK_LENGTH} символов"
    
    keyboard = [
        [InlineKeyboardButton("✍️ Написать отзыв", callback_data="feedback_new")],
        [InlineKeyboardButton("🔙 Назад", callback_data="feedback_back")]
    ]
    
    # Handle both message and callback updates
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
    
    return ConversationHandler.END


async def start_new_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start the process of writing new feedback."""
    await update.callback_query.answer()
    
    message = (
        "✍️ **Напишите ваш отзыв или предложение**\n\n"
        f"Максимальная длина: {MAX_FEEDBACK_LENGTH} символов\n\n"
        "Просто отправьте текстовое сообщение. "
        "Чтобы отменить, нажмите /cancel"
    )
    
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="feedback_cancel")]]
    
    await update.callback_query.edit_message_text(
        message,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    
    return WAITING_FOR_FEEDBACK


async def receive_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle received feedback text."""
    user_id = update.effective_user.id
    text = update.message.text
    
    if len(text) > MAX_FEEDBACK_LENGTH:
        await update.message.reply_text(
            f"⚠️ Текст слишком длинный ({len(text)} символов).\n"
            f"Максимум: {MAX_FEEDBACK_LENGTH} символов.\n\n"
            "Пожалуйста, сократите текст и отправьте снова."
        )
        return WAITING_FOR_FEEDBACK
    
    # Save feedback to database
    try:
        feedback_id = await save_feedback(user_id, text)
        
        await update.message.reply_text(
            f"✅ **Спасибо за ваш отзыв!**\n\n"
            f"Номер обращения: #{feedback_id}\n"
            f"Статус: {get_status_label(0)}\n\n"
            "Мы обязательно рассмотрим ваше сообщение.",
            parse_mode="Markdown"
        )
        
        logger.info(f"User {user_id} submitted feedback #{feedback_id}")
        
    except Exception as e:
        logger.error(f"Error saving feedback for user {user_id}: {e}")
        await update.message.reply_text(
            "❌ Произошла ошибка при сохранении отзыва. "
            "Пожалуйста, попробуйте позже."
        )
    
    return ConversationHandler.END


async def cancel_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel feedback submission."""
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
            "❌ Отправка отзыва отменена.",
            reply_markup=None
        )
    else:
        await update.message.reply_text("❌ Отправка отзыва отменена.")
    
    return ConversationHandler.END


async def feedback_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Go back to main menu."""
    if update.callback_query:
        await update.callback_query.answer()
        # Delete current message and show start
        await update.callback_query.message.delete()
    
    # Create a fake update to call start
    # Or just send a message telling user to use /start
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Используйте /start чтобы вернуться в главное меню."
    )
    
    return ConversationHandler.END


def get_feedback_handler():
    """Get the conversation handler for feedback."""
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(show_feedback_menu, pattern="^feedback_show$"),
            CallbackQueryHandler(start_new_feedback, pattern="^feedback_new$"),
        ],
        states={
            WAITING_FOR_FEEDBACK: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_feedback),
                CallbackQueryHandler(cancel_feedback, pattern="^feedback_cancel$"),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(cancel_feedback, pattern="^feedback_cancel$"),
            CallbackQueryHandler(feedback_back, pattern="^feedback_back$"),
            MessageHandler(filters.COMMAND, cancel_feedback),
        ],
        per_message=False
    )


async def feedback_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle feedback callbacks outside conversation."""
    query = update.callback_query
    data = query.data
    
    if data == "feedback_show":
        await show_feedback_menu(update, context)
    elif data == "feedback_back":
        await feedback_back(update, context)
