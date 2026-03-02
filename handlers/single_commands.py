from telebot import types
from telebot.apihelper import ApiTelegramException
import time
from threading import Lock
import sqlite3
from pathlib import Path
import re

from utils.classify import classify_result
from security.channel_guard import is_channel_subscribed, send_channel_prompt
from storage.repositories.bans import is_banned
from storage.repositories.bin_bans import is_bin_banned
from storage.repositories.credits import get_credits
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

from config.settings import HIT_CHAT, ADMINS


# ======================================================
# CARD EXTRACTOR + VALIDATOR
# ======================================================

def extract_valid_card(text: str):
    if not text:
        return None

    pattern = r'(\d{13,16})[|/:](\d{1,2})[|/:](\d{2,4})[|/:](\d{3,4})'
    match = re.search(pattern, text)

    if not match:
        return None

    number, month, year, cvv = match.groups()

    month = month.zfill(2)
    year = year if len(year) == 4 else "20" + year

    return f"{number}|{month}|{year}|{cvv}"


# ======================================================
# GATES
# ======================================================

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


# ======================================================
# THREAD SAFE SEND
# ======================================================

send_lock = Lock()

def send_hit(bot, chat_id, text):
    with send_lock:
        try:
            bot.send_message(chat_id, text, parse_mode="HTML")
        except Exception as e:
            print(f"[HIT SEND ERROR] {e}")


def safe_edit(bot, chat_id, msg_id, text):
    try:
        bot.edit_message_text(text, chat_id, msg_id, parse_mode="HTML")
    except:
        try:
            bot.send_message(chat_id, text, parse_mode="HTML")
        except:
            pass


def safe_pin(bot, chat_id, msg_id):
    try:
        bot.pin_chat_message(chat_id, msg_id, disable_notification=True)
    except:
        pass


# ======================================================
# REGISTER SINGLE COMMANDS
# ======================================================

def register_single_commands(bot):

    def run_single_check(message, gate_key, card):

        user_id = message.from_user.id
        user_name = get_user_name(message.from_user)

        # 🚫 BANNED
        if is_banned(user_id):
            bot.reply_to(
                message,
                "<b>🚫 YOU ARE BANNED FROM USING THIS BOT</b>",
                parse_mode="HTML"
            )
            return

        gate_display_name, gate_func, gate_type, db_key = SINGLE_GATES[gate_key]

        # ⛔ GATE DISABLED
        if not is_gate_enabled(db_key):
            bot.reply_to(
                message,
                f"<b>⛔ GATE DISABLED</b>\n\n<b>{gate_display_name}</b> is currently closed by admin.",
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

        # 🚫 BIN CHECK
        bin_num = card[:6]
        if is_bin_banned(bin_num):
            bot.reply_to(message, "<b>❌ BIN BANNED</b>", parse_mode="HTML")
            return

        # ⏳ WAIT MESSAGE
        wait_msg = bot.reply_to(
            message,
            "<b>⏳ PLEASE WAIT CHECKING YOUR CARD...</b>",
            parse_mode="HTML"
        )
        msg_id = wait_msg.message_id

        start = time.time()

    try:
        res = gate_func(card)

        if isinstance(res, tuple) and len(res) == 3:
            result, gate_name, func_name = res
        elif isinstance(res, tuple) and len(res) == 2:
            result, gate_name = res
            func_name = ""
        else:
            result = str(res)
            gate_name = gate_display_name
            func_name = ""

    except Exception as e:
            result = f"Gateway Error"
            gate_name = gate_display_name
            func_name = ""

            exec_time = round(time.time() - start, 2)

        # ===== Deduct Credits =====
        if credits != -1:
            from storage.repositories.credits import deduct_credits
            from storage.repositories.gates import get_cost
            cost = get_cost(db_key)
            deduct_credits(user_id, cost)

        # ===== CLASSIFY =====
        status = classify_result(result)

        if status == "CHARGED":
            text = charged_message(card, result, gate_name, exec_time, dato, user_name, func_name)
            hit_type = "charged"
            pin = True

        elif status == "APPROVED":
            text = approved_message(card, result, gate_name, exec_time, dato, user_name, func_name)
            hit_type = "approved"
            pin = True

        elif status == "FUNDS":
            text = insufficient_funds_message(card, result, gate_name, exec_time, dato, user_name, func_name)
            hit_type = "funds"
            pin = True

        else:
            text = declined_message(card, result, gate_name, exec_time, dato, user_name, func_name)
            hit_type = None
            pin = False

        safe_edit(bot, message.chat.id, msg_id, text)

        if pin and message.chat.type != "private":
            safe_pin(bot, message.chat.id, msg_id)

        if hit_type:
            hit_text = hit_detected_message(user_name, hit_type, exec_time, gate_name, "", func_name)
            send_hit(bot, HIT_CHAT, hit_text)


    # ======================================================
    # HANDLER
    # ======================================================

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

        cmd = message.text.split()[0][1:].lower()
        card = None

        # 1️⃣ Card after command
        parts = message.text.strip().split(maxsplit=1)
        if len(parts) == 2:
            card = extract_valid_card(parts[1])

        # 2️⃣ Reply mode
        if not card and message.reply_to_message:
            replied_text = message.reply_to_message.text
            card = extract_valid_card(replied_text)

        # ❌ Wrong format
        if not card:
            bot.reply_to(
                message,
                "<b>❌ Wrong format</b>\n\n",
                parse_mode="HTML"
            )
            return

        # ✅ Valid card
        run_single_check(message, cmd, card)
