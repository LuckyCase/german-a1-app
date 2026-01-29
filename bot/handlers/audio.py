import io
import os
from gtts import gTTS
from telegram import Update
from telegram.ext import ContextTypes

# Cache directory for audio files
AUDIO_CACHE_DIR = "data/audio_cache"


async def send_word_audio(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    """Generate and send audio pronunciation for a word."""
    if not text:
        return

    # Create cache directory if it doesn't exist
    os.makedirs(AUDIO_CACHE_DIR, exist_ok=True)

    # Create a safe filename from the text
    safe_filename = "".join(c if c.isalnum() else "_" for c in text)
    cache_path = os.path.join(AUDIO_CACHE_DIR, f"{safe_filename}.mp3")

    try:
        # Check if we have cached audio
        if os.path.exists(cache_path):
            with open(cache_path, "rb") as audio_file:
                await context.bot.send_voice(
                    chat_id=update.effective_chat.id,
                    voice=audio_file,
                    caption=f"{text}"
                )
        else:
            # Generate audio using gTTS
            tts = gTTS(text=text, lang='de', slow=False)

            # Save to cache
            tts.save(cache_path)

            # Send the audio
            with open(cache_path, "rb") as audio_file:
                await context.bot.send_voice(
                    chat_id=update.effective_chat.id,
                    voice=audio_file,
                    caption=f"{text}"
                )

    except Exception as e:
        # If audio generation fails, just notify the user
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"Не удалось создать аудио: {str(e)}"
        )


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
