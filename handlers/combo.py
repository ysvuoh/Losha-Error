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
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("checker.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ================= Import Gates ==================
from gates.stripe_auth import check as stripe_auth_check
from gates.braintree_auth import check as braintree_auth_check
from gates.shopify_charge import check as shopify_charge_check
from gates.stripe_charge import check as stripe_charge_check
from gates.paypal_donation import check as paypal_donation_check

# ==================== Global ====================
MAX_THREADS = 15
cpu_count = multiprocessing.cpu_count()
max_threads = min(MAX_THREADS, max(1, cpu_count if cpu_count else 1))
executor = ThreadPoolExecutor(max_workers=max_threads)

user_locks = defaultdict(Lock)
sessions = {}
bot_instance = None

class ComboSession:
    def __init__(self, cards, original_filename):
        self.cards = cards
        self.original_filename = original_filename
        self.stop = False
        self.checking = False
        self.approved = 0
        self.charged = 0
        self.funds = 0
        self.declined = 0
        self.checked = 0
        self.approved_cards = []
        self.charged_cards = []
        self.funds_cards = []
        self.lock = Lock()

# تأكد من أن GATES تحتوي على الدوال الفعلية وليس نصوصاً
GATES = {
    "stripe_auth": ("Stripe_Auth", stripe_auth_check, "AUTH"),
    "braintree_auth": ("Braintree_Auth", braintree_auth_check, "AUTH"),
    "shopify_charge": ("Shopify_Charge", shopify_charge_check, "CHARGE"),
    "stripe_charge": ("Stripe_Charge", stripe_charge_check, "CHARGE"),
    "paypal_donation": ("Paypal_Donation", paypal_donation_check, "CHARGE"),
}

MAX_RETRY = 3

def build_progress(percent: int, size: int = 10):
    filled = int((percent / 100) * size)
    return f"{'▰' * filled}{'▱' * (size - filled)} {percent}%"

def register_combo(bot):
    global bot_instance
    bot_instance = bot

    @bot.message_handler(content_types=["document"])
    def receive_combo(message):
        uid = message.from_user.id
        user = message.from_user
        user_name = user.first_name
        
        logger.info(f"User {uid} ({user_name}) uploaded a file.")

        if is_banned(uid):
            bot.send_message(message.chat.id, "<b>🚫 YOU ARE BANNED FROM USING THIS BOT</b>", parse_mode="HTML")
            return

        if not is_channel_subscribed(bot, uid):
            send_channel_prompt(bot, message.chat.id, user_name)
            return

        try:
            file_info = bot.get_file(message.document.file_id)
            raw = bot.download_file(file_info.file_path)
            cards = [c.strip() for c in raw.decode(errors="ignore").splitlines() if c.strip()]
            logger.info(f"File processed: {len(cards)} cards found.")
        except Exception as e:
            logger.error(f"Failed to process file for user {uid}: {e}")
            bot.send_message(message.chat.id, f"<b>❌ FAILED TO PROCESS FILE: {e}</b>", parse_mode="HTML")
            return

        if not cards:
            bot.send_message(message.chat.id, "<b>❌ EMPTY FILE</b>", parse_mode="HTML")
            return

        sessions[uid] = ComboSession(cards, message.document.file_name)

        kb = types.InlineKeyboardMarkup(row_width=1)
        for key, (name, _, _) in GATES.items():
            if is_gate_enabled(key):
                kb.add(types.InlineKeyboardButton(name, callback_data=f"combo:gate:{key}"))

        bot.send_message(message.chat.id, "<b>ϟ CHOOSE THE GATEWAY ϟ</b>", reply_markup=kb, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda c: c.data == "combo:stop")
    def stop_combo(c):
        uid = c.from_user.id
        if uid in sessions:
            sessions[uid].stop = True
            logger.info(f"User {uid} requested to stop the check.")
            bot.answer_callback_query(c.id, "⛔ Stop requested")

    @bot.callback_query_handler(func=lambda c: c.data.startswith("combo:gate:"))
    def start_check(c):
        uid = c.from_user.id
        user_name = get_user_name(c.from_user)
        gate_key = c.data.split(":")[-1]

        session = sessions.get(uid)
        if not session or session.checking:
            bot.answer_callback_query(c.id, "A check is already running or session expired.", show_alert=True)
            return

        if gate_key not in GATES:
            bot.answer_callback_query(c.id, "Invalid Gateway selected.", show_alert=True)
            return

        gate_name, gate_func, gate_type = GATES[gate_key]
        total_limit = len(session.cards) if is_admin(uid) else get_limit(gate_key)
        cost = get_cost(gate_key)

        total = min(len(session.cards), total_limit)
        session.cards = session.cards[:total]

        user_credits = get_credits(uid)
        if not is_admin(uid) and user_credits < cost:
            bot.answer_callback_query(c.id, f"⛔ Not enough credits ({user_credits} < {cost})", show_alert=True)
            return

        session.checking = True
        session.stop = False
        logger.info(f"Starting check for user {uid} on gate {gate_name}. Total cards: {total}")

        chat_id = c.message.chat.id
        message_id = c.message.message_id

        kb = types.InlineKeyboardMarkup(row_width=1)
        kb.add(
            types.InlineKeyboardButton("━ 𝗖𝗖 • 𝗪𝗔𝗜𝗧𝗜𝗡𝗚...", callback_data="x"),
            types.InlineKeyboardButton("━ 𝗦𝗧𝗔𝗧𝗨𝗦 • 𝗪𝗔𝗜𝗧𝗜𝗡𝗚...", callback_data="x"),
            types.InlineKeyboardButton(f"━ {'𝗔𝗣𝗣𝗥𝗢𝗩𝗘𝗗 ✅' if gate_type == 'AUTH' else '𝗖𝗛𝗔𝗥𝗚𝗘𝗗 ⚡'} • 0", callback_data="x"),
            types.InlineKeyboardButton(f"━ {'𝗗𝗘𝗖𝗟𝗜𝗡𝗘𝗗 ❌' if gate_type == 'AUTH' else '𝗙𝗨𝗡𝗗𝗦 💸'} • 0", callback_data="x"),
            types.InlineKeyboardButton(f"━ 𝗧𝗢𝗧𝗔𝗟 ⚡ • 0 / {total}", callback_data="x"),
            types.InlineKeyboardButton("⛔ 𝗦𝗧𝗢𝗣 𝗖𝗛𝗘𝗖𝗞", callback_data="combo:stop"),
        )

        bot.edit_message_text(
            f"<b>PLEASE WAIT CHECKING YOUR CARDS 💫\nGATE ➜ {gate_name}\n\n━━━━━━━━━━━━━━━━━━━━━━━\n{build_progress(0)}\n━━━━━━━━━━━━━━━━━━━━━━━</b>",
            chat_id, message_id, reply_markup=kb, parse_mode="HTML"
        )

        executor.submit(run_check, uid, chat_id, message_id, gate_key, total, cost, user_name)

def run_check(uid, chat_id, message_id, gate_key, total, cost, user_name):
    session = sessions.get(uid)
    if not session: return

    gate_name, gate_func, gate_type = GATES[gate_key]
    last_update_time = time.time()

    try:
        for i, card in enumerate(session.cards):
            if session.stop:
                logger.info(f"Check stopped for user {uid} at card {i}.")
                break

            current_credits = get_credits(uid)
            if not is_admin(uid) and current_credits < cost:
                session.stop = True
                logger.warning(f"User {uid} ran out of credits during check.")
                bot_instance.send_message(chat_id, "<b>⚠️ CHECK STOPPED - INSUFFICIENT CREDITS</b>", parse_mode="HTML")
                break

            r_text = "Unknown Error"
            try:
                for attempt in range(MAX_RETRY):
                    try:
                        # التأكد من أن gate_func هي دالة قابلة للاستدعاء
                        if callable(gate_func):
                            response = gate_func(card)
                            r_text = str(response) if response else "Empty Response"
                        else:
                            r_text = f"Internal Error: {gate_name} function not found"
                            logger.error(f"Gate function for {gate_name} is not callable: {type(gate_func)}")
                            break
                        
                        if r_text and "error" not in r_text.lower():
                            break
                        else:
                            logger.warning(f"Attempt {attempt+1} failed for card {card}: {r_text}")
                    except Exception as gate_err:
                        r_text = f"Gate Exception: {str(gate_err)}"
                        logger.error(f"Exception in gate {gate_name} for card {card}: {gate_err}")
                    time.sleep(1)
            except Exception as e:
                r_text = f"Critical Gate Error: {str(e)}"
                logger.critical(f"Critical error in run_check loop for card {card}: {e}")

            try:
                status = classify_result(r_text)
            except Exception as e:
                logger.error(f"Classification failed for response '{r_text}': {e}")
                status = "DECLINED"

            message_to_send = None
            hit_type = None

            with session.lock:
                if status == "CHARGED":
                    session.charged += 1
                    session.charged_cards.append(card)
                    message_to_send = charged_message(card, r_text, gate_name, 0, user_name)
                    hit_type = "charged"
                elif status == "APPROVED":
                    session.approved += 1
                    session.approved_cards.append(card)
                    message_to_send = approved_message(card, r_text, gate_name, 0, user_name)
                    hit_type = "approved"
                elif status == "FUNDS":
                    session.funds += 1
                    session.funds_cards.append(card)
                    message_to_send = insufficient_funds_message(card, r_text, gate_name, 0, user_name)
                    hit_type = "funds"
                else:
                    session.declined += 1

                session.checked += 1

            if message_to_send:
                try:
                    bot_instance.send_message(chat_id, message_to_send, parse_mode="HTML")
                    bot_instance.send_message(HIT_CHAT, hit_detected_message(user_name, hit_type, 0, gate_name), parse_mode="HTML")
                except Exception as e:
                    logger.error(f"Error sending hit message for user {uid}: {e}")

            if not is_admin(uid) and "error" not in r_text.lower():
                try:
                    with user_locks[uid]:
                        deduct_credits(uid, cost)
                except Exception as e:
                    logger.error(f"Failed to deduct credits for user {uid}: {e}")

            if time.time() - last_update_time >= 2:
                last_update_time = time.time()
                update_progress_ui(uid, chat_id, message_id, card, r_text, gate_name, total, gate_type)

    except Exception as global_err:
        logger.critical(f"Global error in run_check for user {uid}: {global_err}")
    finally:
        session.checking = False
        update_progress_ui(uid, chat_id, message_id, "N/A", "Finished", gate_name, total, gate_type, force_update=True)
        summary_text = f"<b>✨ CHECK SUMMARY ✨</b>\n" \
                       f"━━━━━━━━━━━━━━━━━━\n" \
                       f"Approved  ✅ : {session.approved}\n" \
                       f"Charged   ⚡ : {session.charged}\n" \
                       f"Funds     💸 : {session.funds}\n" \
                       f"Declined  ❌ : {session.declined}\n" \
                       f"━━━━━━━━━━━━━━━━━━\n" \
                       f"Processed : {session.checked} / {total}\n" \
                       f"━━━━━━━━━━━━━━━━━━"
        try:
            bot_instance.send_message(chat_id, summary_text, parse_mode="HTML")
            send_result_files(uid, chat_id)
        except Exception as e:
            logger.error(f"Failed to send summary/files for user {uid}: {e}")

def update_progress_ui(uid, chat_id, message_id, card, status, gate_name, total, gate_type, force_update=False):
    session = sessions.get(uid)
    if not session: return

    percent = int((session.checked / total) * 100) if total > 0 else 0

    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton(f"━ 𝗖𝗖 • {card}", callback_data="x"),
        types.InlineKeyboardButton(f"━ 𝗦𝗧𝗔𝗧𝗨𝗦 • {status}", callback_data="x"),
        types.InlineKeyboardButton(f"━ {'𝗔𝗣𝗣𝗥𝗢𝗩𝗘𝗗 ✅' if gate_type == 'AUTH' else '𝗖𝗛𝗔𝗥𝗚𝗘𝗗 ⚡'} • {session.approved if gate_type == 'AUTH' else session.charged}", callback_data="x"),
        types.InlineKeyboardButton(f"━ {'𝗗𝗘𝗖𝗟𝗜𝗡𝗘𝗗 ❌' if gate_type == 'AUTH' else '𝗙𝗨𝗡𝗗𝗦 💸'} • {session.declined if gate_type == 'AUTH' else session.funds}", callback_data="x"),
        types.InlineKeyboardButton(f"━ 𝗧𝗢𝗧𝗔𝗟 ⚡ • {session.checked} / {total}", callback_data="x"),
        types.InlineKeyboardButton("⛔ 𝗦𝗧𝗢𝗣 𝗖𝗛𝗘𝗖𝗞", callback_data="combo:stop"),
    )

    try:
        bot_instance.edit_message_text(
            f"<b>PLEASE WAIT CHECKING YOUR CARDS 💫\nGATE ➜ {gate_name}\n\n━━━━━━━━━━━━━━━━━━━━━━━\n{build_progress(percent)}\n━━━━━━━━━━━━━━━━━━━━━━━</b>",
            chat_id, message_id, reply_markup=kb, parse_mode="HTML"
        )
    except Exception:
        pass

def send_result_files(uid, chat_id):
    session = sessions.get(uid)
    if not session: return

    files_to_send = [
        (session.approved_cards, "Approved.txt"),
        (session.charged_cards, "Charged.txt"),
        (session.funds_cards, "Funds.txt")
    ]

    for cards, filename in files_to_send:
        if cards:
            try:
                content = "\n".join(cards)
                bio = io.BytesIO(content.encode())
                bio.name = filename
                bot_instance.send_document(chat_id, bio)
            except Exception as e:
                logger.error(f"Error sending file {filename} to user {uid}: {e}")
