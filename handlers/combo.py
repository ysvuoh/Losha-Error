import time
import io
import multiprocessing
from concurrent.futures import ThreadPoolExecutor
from telebot import types
from collections import defaultdict
from threading import Lock
from datetime import datetime

from utils.admin_guard import is_admin
from utils.classify import classify_result
from utils.messages import (
    approved_message,
    charged_message,
    insufficient_funds_message,
    hit_detected_message,
    get_user_name
)

from storage.repositories.bans import is_banned
from storage.repositories.credits import get_credits, ensure_row, deduct_credits
from storage.repositories.gates import is_gate_enabled, get_limit, get_cost
from security.channel_guard import is_channel_subscribed, send_channel_prompt
from config.settings import ADMIN_GROUP, HIT_CHAT

# ================= Gates =================
from gates.stripe_auth import check as stripe_auth_check
from gates.braintree_auth import check as braintree_auth_check
from gates.shopify_charge import check as shopify_charge_check
from gates.stripe_charge import check as stripe_charge_check
from gates.paypal_donation import check as paypal_donation_check

# ================= Global =================
MAX_THREADS = 15
executor = ThreadPoolExecutor(
    max_workers=min(MAX_THREADS, multiprocessing.cpu_count())
)

sessions = {}
user_locks = defaultdict(Lock)
bot_instance = None


class ComboSession:
    def __init__(self, cards, filename):
        self.cards = cards
        self.filename = filename
        self.checking = False
        self.stop = False

        self.checked = 0
        self.approved = 0
        self.charged = 0
        self.funds = 0
        self.declined = 0

        self.approved_cards = []
        self.charged_cards = []
        self.funds_cards = []
        self.lock = Lock()


GATES = {
    "stripe_auth": ("Stripe Auth", stripe_auth_check, "AUTH"),
    "braintree_auth": ("Braintree Auth", braintree_auth_check, "AUTH"),
    "shopify_charge": ("Shopify Charge", shopify_charge_check, "CHARGE"),
    "stripe_charge": ("Stripe Charge", stripe_charge_check, "CHARGE"),
    "paypal_donation": ("Paypal Donation", paypal_donation_check, "CHARGE"),
}

# =====================================================

def build_progress(p, size=10):
    f = int((p / 100) * size)
    return f"{'▰'*f}{'▱'*(size-f)} {p}%"


def register_combo(bot):
    global bot_instance
    bot_instance = bot

    # ================= RECEIVE FILE =================
    @bot.message_handler(content_types=["document"])
    def receive_combo(message):
        uid = message.from_user.id
        user_name = message.from_user.first_name

        if is_banned(uid):
            bot.send_message(message.chat.id, "🚫 You are banned")
            return

        if not is_channel_subscribed(bot, uid):
            send_channel_prompt(bot, message.chat.id, user_name)
            return

        if not message.document.file_name.lower().endswith(".txt"):
            bot.send_message(message.chat.id, "❌ Only .txt files allowed")
            return

        wait = bot.send_message(message.chat.id, "⏳ Processing combo file...")

        file_info = bot.get_file(message.document.file_id)
        raw = bot.download_file(file_info.file_path)
        cards = [c.strip() for c in raw.decode(errors="ignore").splitlines() if c.strip()]

        if not cards:
            bot.edit_message_text("❌ Empty file", message.chat.id, wait.message_id)
            return

        ensure_row(uid)
        sessions[uid] = ComboSession(cards, message.document.file_name)

        kb = types.InlineKeyboardMarkup()
        for k, (n, _, _) in GATES.items():
            if is_gate_enabled(k):
                kb.add(types.InlineKeyboardButton(n, callback_data=f"combo:gate:{k}"))

        bot.edit_message_text(
            "⚡ Choose Gateway",
            message.chat.id,
            wait.message_id,
            reply_markup=kb
        )

    # ================= START CHECK =================
    @bot.callback_query_handler(func=lambda c: c.data.startswith("combo:gate:"))
    def start_check(c):
        uid = c.from_user.id
        session = sessions.get(uid)

        if not session or session.checking:
            return

        gate_key = c.data.split(":")[-1]
        gate_name, gate_func, gate_type = GATES[gate_key]
        cost = get_cost(gate_key)

        # ========= حساب عدد الكروت =========
        total_cards = len(session.cards)

        if not is_admin(uid):
            total_cards = min(total_cards, get_limit(gate_key))
            max_by_credits = get_credits(uid) // cost

            if max_by_credits <= 0:
                bot.answer_callback_query(c.id, "⛔ نقاطك غير كافية", show_alert=True)
                return

            total_cards = min(total_cards, max_by_credits)

        if total_cards < len(session.cards):
            bot.send_message(
                c.message.chat.id,
                f"ℹ️ سيتم فحص أول {total_cards} بطاقة فقط حسب الحد / النقاط"
            )

        session.cards = session.cards[:total_cards]
        session.checking = True

        bot.edit_message_text(
            f"🚀 Starting check\nGate: {gate_name}\n\n{build_progress(0)}",
            c.message.chat.id,
            c.message.message_id
        )

        executor.submit(run_check, uid, c.message.chat.id, c.message.message_id, gate_key)

# =====================================================

def run_check(uid, chat_id, msg_id, gate_key):
    session = sessions.get(uid)
    gate_name, gate_func, gate_type = GATES[gate_key]
    cost = get_cost(gate_key)

    for card in session.cards:
        if session.stop:
            break

        if not is_admin(uid) and get_credits(uid) < cost:
            bot_instance.send_message(chat_id, "⚠️ نقاطك خلصت، تم إيقاف الفحص")
            break

        start = time.time()
        try:
            result = str(gate_func(card))
        except:
            result = "error"

        status = classify_result(result)
        exec_time = round(time.time() - start, 2)

        with session.lock:
            session.checked += 1

            if status == "APPROVED":
                session.approved += 1
                session.approved_cards.append(card)
                bot_instance.send_message(
                    chat_id,
                    approved_message(card, result, gate_name, exec_time, get_user_name(uid)),
                    parse_mode="HTML"
                )

            elif status == "CHARGED":
                session.charged += 1
                session.charged_cards.append(card)
                bot_instance.send_message(
                    chat_id,
                    charged_message(card, result, gate_name, exec_time, get_user_name(uid)),
                    parse_mode="HTML"
                )

            elif status == "FUNDS":
                session.funds += 1
                session.funds_cards.append(card)

            else:
                session.declined += 1

        if not is_admin(uid) and "error" not in result.lower():
            deduct_credits(uid, cost)

        percent = int((session.checked / len(session.cards)) * 100)
        try:
            bot_instance.edit_message_text(
                f"⏳ Checking...\nGate: {gate_name}\n\n{build_progress(percent)}",
                chat_id,
                msg_id
            )
        except:
            pass

    session.checking = False
    bot_instance.send_message(
        chat_id,
        f"✅ Finished\n"
        f"Approved: {session.approved}\n"
        f"Charged: {session.charged}\n"
        f"Funds: {session.funds}\n"
        f"Declined: {session.declined}\n"
        f"Checked: {session.checked}"
    )

    send_result_files(uid, chat_id)


def send_result_files(uid, chat_id):
    s = sessions.get(uid)
    if not s:
        return

    if s.approved_cards:
        bio = io.BytesIO("\n".join(s.approved_cards).encode())
        bio.name = "Approved.txt"
        bot_instance.send_document(chat_id, bio)

    if s.charged_cards:
        bio = io.BytesIO("\n".join(s.charged_cards).encode())
        bio.name = "Charged.txt"
        bot_instance.send_document(chat_id, bio)

    if s.funds_cards:
        bio = io.BytesIO("\n".join(s.funds_cards).encode())
        bio.name = "Funds.txt"
        bot_instance.send_document(chat_id, bio)
