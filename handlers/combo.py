import threading
import time
import io
import multiprocessing
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from telebot import types
from utils.admin_guard import is_admin
from storage.repositories.bans import is_banned
from security.channel_guard import is_channel_subscribed, send_channel_prompt
from storage.repositories.credits import get_credits, ensure_row, deduct_credits
from storage.repositories.gates import is_gate_enabled, get_limit, get_cost
from datetime import datetime
from config.settings import ADMIN_GROUP, HIT_CHAT
from utils.classify import classify_result
from utils.messages import (
    approved_message,
    charged_message,
    insufficient_funds_message,
    hit_detected_message,
    get_user_name
)
from collections import defaultdict
from threading import Lock

# ================= Logging Setup =================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("COMBO")

# ================= Import Gates =================
from gates.stripe_auth import check as stripe_auth_check
from gates.braintree_auth import check as braintree_auth_check
from gates.shopify_charge import check as shopify_charge_check
from gates.stripe_charge import check as stripe_charge_check
from gates.paypal_donation import check as paypal_donation_check

# ================= Global =================
MAX_THREADS = 15
cpu_count = multiprocessing.cpu_count()
executor = ThreadPoolExecutor(max_workers=min(MAX_THREADS, max(1, cpu_count)))

user_locks = defaultdict(Lock)
sessions = {}
bot_instance = None

# ================= Session =================
class ComboSession:
    def __init__(self, cards, filename):
        self.cards = cards
        self.filename = filename
        self.stop = False
        self.checking = False
        self.checked = 0
        self.approved = 0
        self.charged = 0
        self.funds = 0
        self.declined = 0
        self.approved_cards = []
        self.charged_cards = []
        self.funds_cards = []
        self.lock = Lock()

# ================= Gates =================
AVAILABLE_GATES = {
    "stripe_auth": {"name": "Stripe_Auth", "func": stripe_auth_check, "type": "AUTH"},
    "braintree_auth": {"name": "Braintree_Auth", "func": braintree_auth_check, "type": "AUTH"},
    "shopify_charge": {"name": "Shopify_Charge", "func": shopify_charge_check, "type": "CHARGE"},
    "stripe_charge": {"name": "Stripe_Charge", "func": stripe_charge_check, "type": "CHARGE"},
    "paypal_donation": {"name": "Paypal_Donation", "func": paypal_donation_check, "type": "CHARGE"},
}

MAX_RETRY = 3

def build_progress(percent, size=10):
    filled = int((percent / 100) * size)
    return f"{'▰'*filled}{'▱'*(size-filled)} {percent}%"

# ================= Combo Registration =================
def register_combo(bot):
    global bot_instance
    bot_instance = bot

    @bot.message_handler(content_types=["document"])
    def receive_combo(message):
        uid = message.from_user.id
        user_name = message.from_user.first_name
        logger.info(f"[UPLOAD] User={uid} Name={user_name}")

        if is_banned(uid):
            bot.send_message(message.chat.id, "BANNED")
            return

        if not is_channel_subscribed(bot, uid):
            send_channel_prompt(bot, message.chat.id, user_name)
            return

        try:
            file_info = bot.get_file(message.document.file_id)
            raw = bot.download_file(file_info.file_path)
            cards = [c.strip() for c in raw.decode(errors="ignore").splitlines() if c.strip()]
            logger.info(f"[FILE] CardsLoaded={len(cards)}")
        except Exception as e:
            logger.error(f"[FILE_ERROR] {e}")
            return

        sessions[uid] = ComboSession(cards, message.document.file_name)

        kb = types.InlineKeyboardMarkup()
        for key, g in AVAILABLE_GATES.items():
            if is_gate_enabled(key):
                kb.add(types.InlineKeyboardButton(g["name"], callback_data=f"combo:gate:{key}"))

        bot.send_message(message.chat.id, "CHOOSE GATE", reply_markup=kb)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("combo:gate:"))
    def start_check(c):
        uid = c.from_user.id
        gate_key = c.data.split(":")[-1]
        session = sessions.get(uid)

        if not session or session.checking:
            return

        gate = AVAILABLE_GATES[gate_key]
        total = len(session.cards)
        cost = get_cost(gate_key)

        session.checking = True
        logger.info(f"[START] User={uid} Gate={gate['name']} Cards={total}")

        executor.submit(
            run_check,
            uid,
            c.message.chat.id,
            c.message.message_id,
            gate_key,
            total,
            cost,
            get_user_name(c.from_user)
        )

# ================= Run Check =================
def run_check(uid, chat_id, message_id, gate_key, total, cost, user_name):
    session = sessions.get(uid)
    gate = AVAILABLE_GATES[gate_key]
    gate_func = gate["func"]

    if not callable(gate_func):
        logger.critical(f"[FATAL] Gate not callable: {gate_key}")
        return

    for i, card in enumerate(session.cards):
        logger.info(f"[LOOP] {i+1}/{total} Card={card}")

        if session.stop:
            logger.warning("[STOP] Requested by user")
            break

        credits = get_credits(uid)
        if not is_admin(uid) and credits < cost:
            logger.warning(f"[STOP] No credits ({credits} < {cost})")
            break

        r_text = "NO_RESPONSE"

        for attempt in range(1, MAX_RETRY + 1):
            try:
                logger.debug(f"[GATE] Try={attempt}")
                r = gate_func(card)
                r_text = str(r)
                break
            except Exception as e:
                r_text = f"GATE_EXCEPTION: {e}"
                logger.error(r_text)
                time.sleep(1)

        try:
            status = classify_result(r_text)
        except Exception as e:
            logger.error(f"[CLASSIFY_ERROR] {e}")
            status = "DECLINED"

        logger.info(f"[RESULT] Status={status} Raw='{r_text[:120]}'")

        with session.lock:
            if status == "APPROVED":
                session.approved += 1
                session.approved_cards.append(card)
            elif status == "CHARGED":
                session.charged += 1
                session.charged_cards.append(card)
            elif status == "FUNDS":
                session.funds += 1
                session.funds_cards.append(card)
            else:
                session.declined += 1

            session.checked += 1

            logger.debug(
                f"[COUNTERS] checked={session.checked} "
                f"approved={session.approved} charged={session.charged} "
                f"funds={session.funds} declined={session.declined}"
            )

        if not is_admin(uid):
            with user_locks[uid]:
                deduct_credits(uid, cost)

        logger.info("[CONTINUE] Next card")

    logger.info(f"[FINISH] User={uid} Checked={session.checked}/{total}")
    send_result_files(uid, chat_id)

# ================= Result Files =================
def send_result_files(uid, chat_id):
    session = sessions.get(uid)
    if not session:
        return

    files = [
        (session.approved_cards, "Approved.txt"),
        (session.charged_cards, "Charged.txt"),
        (session.funds_cards, "Funds.txt"),
    ]

    for cards, name in files:
        if cards:
            bio = io.BytesIO("\n".join(cards).encode())
            bio.name = name
            bot_instance.send_document(chat_id, bio)
