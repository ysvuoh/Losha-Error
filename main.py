import os
import sys
import time
import signal
import logging
from dotenv import load_dotenv
from core.bot import create_bot
from handlers import register_all
from storage.db import init_db
from storage.repositories.gates import init_gates


# =========================
# ENV LOADING & VALIDATION
# =========================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(BASE_DIR, ".env")

if not os.path.exists(ENV_PATH):
    print("❌ .env file not found. Aborting startup.")
    sys.exit(1)

load_dotenv(ENV_PATH)

BOT_TOKEN = os.getenv("BOT_TOKEN")
ENV_MODE = os.getenv("ENV", "prod").lower()

if not BOT_TOKEN:
    print("❌ BOT_TOKEN is missing in .env")
    sys.exit(1)


# =========================
# LOGGING SETUP
# =========================

def setup_logging():
    level = logging.DEBUG if ENV_MODE == "dev" else logging.INFO

    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


# =========================
# GLOBALS
# =========================

logger = logging.getLogger("MAIN")
bot_instance = None


# =========================
# SIGNAL HANDLING
# =========================

def shutdown_handler(signum, frame):
    logger.warning(f"Received signal {signum}. Shutting down gracefully...")

    if bot_instance:
        try:
            bot_instance.stop_polling()
        except Exception:
            logger.exception("Error while stopping bot")

    sys.exit(0)


signal.signal(signal.SIGINT, shutdown_handler)
signal.signal(signal.SIGTERM, shutdown_handler)


# =========================
# STARTUP SEQUENCE
# =========================

def startup():
    logger.info("Starting bot initialization sequence...")

    # ---- INIT DATABASE ----
    try:
        init_db()
        logger.info("Database initialized successfully")
    except Exception:
        logger.exception("Database initialization failed")
        sys.exit(1)

    # ---- INIT GATES ----
    try:
        init_gates()
        logger.info("Gates initialized successfully")
    except Exception:
        logger.exception("Gates initialization failed")
        sys.exit(1)

    # ---- CREATE BOT ----
    try:
        bot = create_bot()
        logger.info("Bot instance created")
    except Exception:
        logger.exception("Bot creation failed (check BOT_TOKEN / API)")
        sys.exit(1)

    # ---- REGISTER HANDLERS ----
    try:
        register_all(bot)
        logger.info("Handlers registered successfully")
    except Exception:
        logger.exception("Handler registration failed")
        sys.exit(1)

    return bot


# =========================
# MAIN
# =========================

from utils.proxy_manager import load_and_clean_proxies, activate_proxy_patching

def main():
    global bot_instance

    setup_logging()
    
    # ---- ACTIVATE PROXIES ----
    load_and_clean_proxies()
    activate_proxy_patching()
    logger.info(f"Environment mode: {ENV_MODE.upper()}")

    bot_instance = startup()

    logger.info("Bot is running...")

    # IMPORTANT: ensure no webhook conflict
    bot_instance.remove_webhook()

    # SINGLE polling instance (NO LOOP)
    bot_instance.infinity_polling(
        skip_pending=True,
        none_stop=True,
        timeout=60,
        long_polling_timeout=60
    )


# =========================
# ENTRY POINT
# =========================

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.warning("Bot stopped manually")
        sys.exit(0)
    except Exception:
        logger.exception("Fatal startup error")
        sys.exit(1)
