import asyncio
import logging
from typing import Optional
from telegram.ext import Application, ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from telegram.constants import ParseMode

from app.config import settings
from app.services.alert_service import set_telegram_sender
from app.bot.handlers import start_command, callback_query_handler, message_handler

logger = logging.getLogger("powerk.bot")

_bot_app: Optional[Application] = None


async def send_telegram_message(chat_id: int, text: str):
    if _bot_app and _bot_app.bot:
        try:
            await _bot_app.bot.send_message(chat_id=chat_id, text=text, parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            logger.error(f"Failed to send telegram message to {chat_id}: {e}")


def get_bot_app() -> Optional[Application]:
    global _bot_app
    token = settings.TELEGRAM_BOT_TOKEN
    if not token or not settings.TELEGRAM_ENABLED:
        logger.warning("Telegram Bot is disabled or no token was provided.")
        return None

    if _bot_app is None:
        builder = ApplicationBuilder().token(token)
        _bot_app = builder.build()

        _bot_app.add_handler(CommandHandler("start", start_command))
        _bot_app.add_handler(CallbackQueryHandler(callback_query_handler))
        _bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

        # Register message sender with AlertService
        set_telegram_sender(send_telegram_message)

    return _bot_app


async def start_bot():
    app = get_bot_app()
    if not app:
        return
    logger.info("Starting Telegram Bot long-polling...")
    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)


async def stop_bot():
    global _bot_app
    if _bot_app:
        logger.info("Stopping Telegram Bot...")
        if _bot_app.updater and _bot_app.updater.running:
            await _bot_app.updater.stop()
        if _bot_app.running:
            await _bot_app.stop()
        await _bot_app.shutdown()
        _bot_app = None
