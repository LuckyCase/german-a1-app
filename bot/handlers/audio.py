import hashlib
import io
import logging
import os
from pathlib import Path

from gtts import gTTS
from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

# Prefer /tmp on Render (ephemeral but fast); fall back to local dir
_CACHE_DIR = Path(os.getenv("AUDIO_CACHE_DIR", "/tmp/audio_cache"))
_CACHE_DIR.mkdir(parents=True, exist_ok=True)
_MAX_CACHE_FILES = 5000


def _cache_path(text: str) -> Path:
    key = hashlib.sha256(text.encode()).hexdigest()[:16]
    return _CACHE_DIR / f"{key}.mp3"


def _get_audio_bytes(text: str) -> bytes:
    """Return mp3 bytes for *text*, using file cache when possible."""
    path = _cache_path(text)
    if path.exists():
        return path.read_bytes()

    tts = gTTS(text=text, lang="de", slow=False)
    buf = io.BytesIO()
    tts.write_to_fp(buf)
    data = buf.getvalue()

    try:
        if sum(1 for _ in _CACHE_DIR.iterdir()) < _MAX_CACHE_FILES:
            path.write_bytes(data)
    except OSError:
        pass

    return data


async def send_word_audio(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    """Generate and send audio pronunciation for a word (with file cache).

    Returns:
        Message: The sent voice message, or None if failed.
    """
    if not text:
        return None

    try:
        chat_id = update.effective_chat.id

        audio_data = _get_audio_bytes(text)
        audio_buffer = io.BytesIO(audio_data)
        audio_buffer.name = "audio.mp3"

        message = await context.bot.send_voice(
            chat_id=chat_id,
            voice=audio_buffer,
            caption=f"{text}",
        )
        return message

    except Exception as e:
        logger.warning("Audio generation failed for %r: %s", text, e)
        try:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"Не удалось создать аудио: {str(e)}",
            )
        except Exception:
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
