import os
import logging
import telebot
from telebot import apihelper


def create_bot():
    logger = logging.getLogger("BOT")

    # =========================
    # ENV VALIDATION
    # =========================
    token = os.getenv("BOT_TOKEN")
    if not token:
        logger.critical("BOT_TOKEN not set in environment")
        raise RuntimeError("BOT_TOKEN not set")

    # =========================
    # TELEGRAM API HARDENING
    # =========================
    apihelper.ENABLE_MIDDLEWARE = True
    apihelper.REQUEST_TIMEOUT = 20        # seconds
    apihelper.CONNECT_TIMEOUT = 10
    apihelper.READ_TIMEOUT = 20
    apihelper.RETRY_ON_ERROR = True
    apihelper.MAX_RETRIES = 5

    # =========================
    # CREATE BOT INSTANCE
    # =========================
    bot = telebot.TeleBot(
        token=token,
        parse_mode="HTML",
        disable_web_page_preview=True,
        threaded=True,
        num_threads=8   # ⬅️ تحكم في الضغط (مهم)
    )

    # =========================
    # GLOBAL ERROR HANDLER
    # =========================
    @bot.middleware_handler(update_types=["message", "callback_query"])
    def global_error_middleware(bot_instance, update):
        try:
            yield
        except Exception as e:
            logger.exception("Unhandled exception in handler")
            try:
                if hasattr(update, "message") and update.message:
                    bot_instance.send_message(
                        update.message.chat.id,
                        "⚠️ حصل خطأ غير متوقع، حاول مرة تانية"
                    )
            except Exception:
                pass

    logger.info("TeleBot instance created and hardened")
    return bot