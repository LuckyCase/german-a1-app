"""
Error monitoring: Sentry integration + Telegram fallback notifications.

Call `init_sentry()` once at startup.  Use `notify_error()` to send
critical errors to admin Telegram chats when Sentry is unavailable.
"""

import logging
import traceback

from bot.config import SENTRY_DSN

logger = logging.getLogger(__name__)
_sentry_enabled = False


def init_sentry() -> bool:
    """Initialise Sentry SDK if SENTRY_DSN is configured. Returns True on success."""
    global _sentry_enabled
    if not SENTRY_DSN:
        logger.info("SENTRY_DSN not set — Sentry disabled.")
        return False

    try:
        import sentry_sdk
        from sentry_sdk.integrations.flask import FlaskIntegration

        sentry_sdk.init(
            dsn=SENTRY_DSN,
            integrations=[FlaskIntegration()],
            traces_sample_rate=0.1,
            send_default_pii=False,
        )
        _sentry_enabled = True
        logger.info("Sentry initialised.")
        return True
    except Exception as exc:
        logger.warning("Failed to initialise Sentry: %s", exc)
        return False


async def notify_admins_error(bot, error: Exception, context_info: str = ""):
    """Send a short error summary to every admin via Telegram.

    This is the fallback when Sentry is not configured or for immediate
    visibility of critical bot errors.
    """
    from bot.config import ADMIN_IDS

    if not ADMIN_IDS:
        return

    tb = "".join(traceback.format_exception(type(error), error, error.__traceback__))
    if len(tb) > 1500:
        tb = tb[:1500] + "\n…(truncated)"

    text = f"⚠️ Bot error\n{context_info}\n\n<pre>{tb}</pre>"

    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                chat_id=admin_id, text=text, parse_mode="HTML",
            )
        except Exception:
            logger.debug("Could not notify admin %s", admin_id)


def telegram_error_handler_factory():
    """Return an async error handler compatible with python-telegram-bot."""

    async def _error_handler(update, context):
        logger.error("Unhandled exception: %s", context.error, exc_info=context.error)

        if _sentry_enabled:
            import sentry_sdk
            sentry_sdk.capture_exception(context.error)

        info = ""
        if update and update.effective_user:
            info = f"user={update.effective_user.id}"

        try:
            await notify_admins_error(context.bot, context.error, info)
        except Exception:
            pass

    return _error_handler
