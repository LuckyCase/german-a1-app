import io
from gtts import gTTS
from telegram import Update
from telegram.ext import ContextTypes


async def send_word_audio(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    """Generate and send audio pronunciation for a word.

    Generates audio on-the-fly using gTTS without file caching.

    Returns:
        Message: The sent voice message, or None if failed.
    """
    if not text:
        return None

    try:
        chat_id = update.effective_chat.id

        # Generate audio directly to memory
        tts = gTTS(text=text, lang='de', slow=False)
        audio_buffer = io.BytesIO()
        tts.write_to_fp(audio_buffer)
        audio_buffer.seek(0)
        audio_buffer.name = "audio.mp3"

        message = await context.bot.send_voice(
            chat_id=chat_id,
            voice=audio_buffer,
            caption=f"{text}"
        )
        return message

    except Exception as e:
        # If audio generation fails, just notify the user
        try:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"Не удалось создать аудио: {str(e)}"
            )
        except:
            pass
        return None


async def audio_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /audio command to pronounce any German text."""
    if not context.args:
        await update.message.reply_text(
            "Используйте: /audio <немецкий текст>\n"
            "Пример: /audio Guten Tag"
        )
        return

    text = " ".join(context.args)
    await send_word_audio(update, context, text)
