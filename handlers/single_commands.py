from telebot import types
from telebot.apihelper import ApiTelegramException
import time
from threading import Lock
import sqlite3
from pathlib import Path
from utils.classify import classify_result
from security.channel_guard import is_channel_subscribed, send_channel_prompt
from storage.repositories.bans import is_banned
from storage.repositories.credits import get_credits, deduct_one_atomic
from storage.repositories.gates import is_gate_enabled

from utils.messages import (
    approved_message,
    charged_message,
    insufficient_funds_message,
    declined_message,
    hit_detected_message,
    dato,
    get_user_name
)

from config.settings import HIT_CHAT

# ===== DATABASE PATH =====
DB_PATH = Path(__file__).parent.parent / "db.sqlite"  # تعديل المسار ليتوافق مع الهيكل
def get_connection():
    return sqlite3.connect(DB_PATH, isolation_level=None)

# ===== HIT COUNTER =====
hit_counter_lock = Lock()

def get_next_hit_number():
    with hit_counter_lock:
        conn = get_connection()
        cur = conn.cursor()
        # تأكد من وجود جدول hit_counter
        cur.execute("""
            CREATE TABLE IF NOT EXISTS hit_counter (
                id INTEGER PRIMARY KEY CHECK (id=1),
                last_hit INTEGER NOT NULL DEFAULT 0
            )
        """)
        cur.execute("INSERT OR IGNORE INTO hit_counter (id, last_hit) VALUES (1, 0)")

        # اقرأ آخر هيت
        cur.execute("SELECT last_hit FROM hit_counter WHERE id=1")
        row = cur.fetchone()
        last_hit = row[0] if row else 0

        # زود العداد
        next_hit = last_hit + 1
        cur.execute("UPDATE hit_counter SET last_hit=? WHERE id=1", (next_hit,))

        conn.commit()
        conn.close()
        return next_hit

# ===== GATES =====
from gates.stripe_auth import check as stripe_auth_check
from gates.shopify_charge import check as shopify_charge_check
from gates.braintree_auth import check as braintree_auth_check
from gates.stripe_charge import check as stripe_charge_check
from gates.paypal_donation import check as paypal_donation_check

SINGLE_GATES = {
    "str": ("Stripe_Auth", stripe_auth_check, "AUTH", "stripe_auth"),
    "sh":  ("Shopify_Charge", shopify_charge_check, "CHARGE", "shopify_charge"),
    "br":  ("Braintree_Auth", braintree_auth_check, "AUTH", "braintree_auth"),
    "st":  ("Stripe_Charge", stripe_charge_check, "CHARGE", "stripe_charge"),
    "pp":  ("Paypal_Donation", paypal_donation_check, "CHARGE", "paypal_donation"),
}

# ===== THREAD SAFE SEND =====
send_lock = Lock()

def send_hit(bot, chat_id, text):
    with send_lock:
        try:
            bot.send_message(chat_id, text, parse_mode="HTML")
        except Exception as e:
            print(f"[HIT SEND ERROR] {e}")

# ===== SAFE HELPERS =====
def safe_edit(bot, chat_id, msg_id, text):
    try:
        bot.edit_message_text(
            text,
            chat_id,
            msg_id,
            parse_mode="HTML"
        )
    except ApiTelegramException as e:
        if "Too Many Requests" in str(e):
            time.sleep(3)
        try:
            bot.send_message(chat_id, text, parse_mode="HTML")
        except:
            pass
    except:
        pass

def safe_pin(bot, chat_id, msg_id):
    try:
        bot.pin_chat_message(
            chat_id,
            msg_id,
            disable_notification=True
        )
    except:
        pass

# ===== REGISTER SINGLE COMMANDS =====
def register_single_commands(bot):

    def run_single_check(message, gate_key, card):
        user_id = message.from_user.id
        user_name = get_user_name(message.from_user)
        name = message.from_user.first_name or "Hidden"
        username = message.from_user.username

        # 🚫 BANNED
        if is_banned(user_id):
            bot.reply_to(
                message,
                "<b>🚫 YOU ARE BANNED FROM USING THIS BOT</b>",
                parse_mode="HTML"
            )
            return
            
        if not is_channel_subscribed(bot, user_id):
            send_channel_prompt(bot, message.chat.id, name)
            return
        gate_name, gate_func, gate_type, db_key = SINGLE_GATES[gate_key]

        # ⛔ GATE DISABLED
        if not is_gate_enabled(db_key):
            bot.reply_to(
                message,
                f"<b>⛔ GATE DISABLED</b>\n\n<b>{gate_name}</b> is currently closed by admin.",
                parse_mode="HTML"
            )
            return

        # 💳 CREDITS
        credits = get_credits(user_id)
        if credits == 0:
            bot.reply_to(
                message,
                "<b>❌ YOU HAVE NO CREDITS</b>\n<b>Please buy credits to continue.</b>",
                parse_mode="HTML"
            )
            return

        # ⏳ WAIT
        wait_msg = bot.reply_to(
            message,
            "<b>⏳ PLEASE WAIT CHECKING YOUR CARD...</b>",
            parse_mode="HTML"
        )
        msg_id = wait_msg.message_id

        start = time.time()
        try:
            result = str(gate_func(card))
        except Exception:
            result = "Gateway Error ❌"

        exec_time = round(time.time() - start, 2)
        result_l = result.lower()


        if credits != -1:

            from storage.repositories.credits import deduct_credits
            from storage.repositories.gates import get_cost

            cost_to_deduct = get_cost(db_key)
            deduct_credits(user_id, cost_to_deduct)


        # ===== Classify and Send Result =====
        status = classify_result(result)
        user_text = ""
        hit_type = None
        pin_message = False

        if status == "CHARGED":
            user_text = charged_message(card, result, gate_name, exec_time, dato)
            hit_type = "charged"
            pin_message = True
        
        elif status == "APPROVED":
            user_text = approved_message(card, result, gate_name, exec_time, dato)
            hit_type = "approved"
            pin_message = True

        elif status == "FUNDS":
            user_text = insufficient_funds_message(card, result, gate_name, exec_time, dato)
            hit_type = "funds"
            pin_message = True

        else: # Declined
            user_text = declined_message(card, result, gate_name, exec_time, dato)
            pin_message = False

        # Send the final message to the user
        safe_edit(bot, message.chat.id, msg_id, user_text)

        # Pin if it was a hit in a group chat
        if pin_message and message.chat.type != "private":
            safe_pin(bot, message.chat.id, msg_id)

        # Send hit notification to the hit channel
        if hit_type:
            hit_text = hit_detected_message(user_name, hit_type, exec_time, gate_name)
            send_hit(bot, HIT_CHAT, hit_text)


    # ===== HANDLER =====
    @bot.message_handler(
        func=lambda m: (
            m.text and (
                (m.text.startswith(".") and m.text.split()[0][1:].lower() in SINGLE_GATES)
                or
                (m.text.startswith("/") and m.text.split()[0][1:].lower() in SINGLE_GATES)
            )
        )
    )
    def single_handler(message):
        parts = message.text.strip().split(maxsplit=1)
        if len(parts) != 2:
            return

        cmd = parts[0][1:].lower()
        card = parts[1]

        run_single_check(message, cmd, card)
