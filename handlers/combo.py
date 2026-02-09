import threading
import time
import io
import multiprocessing
import logging
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
from utils.messages import get_user_name
from collections import defaultdict
from threading import Lock

# ================= LOGGING =================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger("COMBO")

# ================= GATES =================
from gates.stripe_auth import check as stripe_auth_check
from gates.braintree_auth import check as braintree_auth_check
from gates.shopify_charge import check as shopify_charge_check
from gates.stripe_charge import check as stripe_charge_check
from gates.paypal_donation import check as paypal_donation_check

# ================= GLOBAL =================
MAX_THREADS = 15
executor = ThreadPoolExecutor(max_workers=MAX_THREADS)
user_locks = defaultdict(Lock)
sessions = {}
bot_instance = None

# ================= SESSION =================
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
        self.keyboard = None
        self.msg_id = None
        self.gate_type = None
        self.total = len(cards)

# ================= AVAILABLE GATES =================
AVAILABLE_GATES = {
    "stripe_auth": {"name": "Stripe Auth", "func": stripe_auth_check, "type": "AUTH"},
    "braintree_auth": {"name": "Braintree Auth", "func": braintree_auth_check, "type": "AUTH"},
    "shopify_charge": {"name": "Shopify Charge", "func": shopify_charge_check, "type": "CHARGE"},
    "stripe_charge": {"name": "Stripe Charge", "func": stripe_charge_check, "type": "CHARGE"},
    "paypal_donation": {"name": "Paypal Donation", "func": paypal_donation_check, "type": "CHARGE"},
}

MAX_RETRY = 3

# ================= KEYBOARDS =================
def build_waiting_keyboard(session):
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("━ CC • WAITING ⏳", callback_data="x"),
        types.InlineKeyboardButton("━ STATUS • WAITING ⏳", callback_data="x"),
        types.InlineKeyboardButton("━ APPROVED ✅ • 0", callback_data="x"),
        types.InlineKeyboardButton("━ DECLINED ❌ • 0", callback_data="x"),
        types.InlineKeyboardButton(f"━ TOTAL • 0 / {session.total}", callback_data="x"),
        types.InlineKeyboardButton("⛔ STOP CHECK", callback_data="combo:stop"),
    )
    return kb


def build_running_keyboard(session):
    kb = types.InlineKeyboardMarkup(row_width=1)

    approved = session.approved if session.gate_type == "AUTH" else session.charged
    declined = session.declined if session.gate_type == "AUTH" else session.funds

    kb.add(
        types.InlineKeyboardButton(f"━ CC • {session.checked}/{session.total}", callback_data="x"),
        types.InlineKeyboardButton("━ STATUS • RUNNING ⚙️", callback_data="x"),
        types.InlineKeyboardButton(f"━ APPROVED ✅ • {approved}", callback_data="x"),
        types.InlineKeyboardButton(f"━ DECLINED ❌ • {declined}", callback_data="x"),
        types.InlineKeyboardButton(
            f"━ TOTAL • {session.checked}/{session.total}", callback_data="x"
        ),
        types.InlineKeyboardButton("⛔ STOP CHECK", callback_data="combo:stop"),
    )
    return kb


def build_finished_keyboard(session):
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("━ CC • DONE ✅", callback_data="x"),
        types.InlineKeyboardButton("━ STATUS • FINISHED 🏁", callback_data="x"),
        types.InlineKeyboardButton(f"━ APPROVED ✅ • {session.approved}", callback_data="x"),
        types.InlineKeyboardButton(f"━ DECLINED ❌ • {session.declined}", callback_data="x"),
        types.InlineKeyboardButton(
            f"━ TOTAL • {session.checked}/{session.total}", callback_data="x"
        ),
    )
    return kb

# ================= REGISTER =================
def register_combo(bot):
    global bot_instance
    bot_instance = bot

    @bot.message_handler(content_types=["document"])
    def receive_combo(message):
        uid = message.from_user.id
        logger.info(f"[UPLOAD] UID={uid}")

        if is_banned(uid):
            bot.send_message(message.chat.id, "BANNED")
            return

        if not is_channel_subscribed(bot, uid):
            send_channel_prompt(bot, message.chat.id, message.from_user.first_name)
            return

        file_info = bot.get_file(message.document.file_id)
        raw = bot.download_file(file_info.file_path)
        cards = [c.strip() for c in raw.decode(errors="ignore").splitlines() if c.strip()]

        sessions[uid] = ComboSession(cards, message.document.file_name)
        ensure_row(uid)

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
        session.gate_type = gate["type"]
        session.checking = True

        logger.info(f"[START] UID={uid} GATE={gate_key}")

        session.keyboard = build_waiting_keyboard(session)

        bot.edit_message_text(
            "CHECK INITIALIZED...",
            c.message.chat.id,
            c.message.message_id,
            reply_markup=session.keyboard
        )

        session.msg_id = c.message.message_id

        executor.submit(run_check, uid, c.message.chat.id, gate_key)

    @bot.callback_query_handler(func=lambda c: c.data == "combo:stop")
    def stop_combo(c):
        uid = c.from_user.id
        session = sessions.get(uid)
        if session:
            session.stop = True
            logger.warning(f"[STOP] UID={uid}")
            bot.answer_callback_query(c.id, "Stopped")

    @bot.callback_query_handler(func=lambda c: c.data == "x")
    def ignore(c):
        bot.answer_callback_query(c.id)

# ================= RUN CHECK =================
def run_check(uid, chat_id, gate_key):
    session = sessions.get(uid)
    gate = AVAILABLE_GATES[gate_key]
    cost = get_cost(gate_key)

    logger.info(f"[RUN] UID={uid} TOTAL={session.total}")

    for card in session.cards:
        if session.stop:
            logger.warning("[BREAK] STOPPED")
            break

        if not is_admin(uid) and get_credits(uid) < cost:
            logger.warning("[BREAK] NO CREDITS")
            break

        for attempt in range(1, MAX_RETRY + 1):
            try:
                logger.debug(f"[TRY] {attempt} CARD={card}")
                r = gate["func"](card)
                break
            except Exception as e:
                logger.error(f"[ERROR] {e}")
                time.sleep(1)
        else:
            r = "DECLINED"

        status = classify_result(str(r))
        logger.info(f"[RESULT] {status}")

        with session.lock:
            session.checked += 1
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

            session.keyboard = build_running_keyboard(session)

        if not is_admin(uid):
            with user_locks[uid]:
                deduct_credits(uid, cost)

        bot_instance.edit_message_reply_markup(
            chat_id,
            session.msg_id,
            reply_markup=session.keyboard
        )

    session.keyboard = build_finished_keyboard(session)
    bot_instance.edit_message_reply_markup(
        chat_id,
        session.msg_id,
        reply_markup=session.keyboard
    )

    logger.info("[FINISHED]")
    send_result_files(uid, chat_id)

# ================= RESULTS =================
def send_result_files(uid, chat_id):
    session = sessions.get(uid)
    if not session:
        return

    for data, name in [
        (session.approved_cards, "Approved.txt"),
        (session.charged_cards, "Charged.txt"),
        (session.funds_cards, "Funds.txt"),
    ]:
        if data:
            bio = io.BytesIO("\n".join(data).encode())
            bio.name = name
            bot_instance.send_document(chat_id, bio)
