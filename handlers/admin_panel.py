import os
import io
import sys
import json
from pathlib import Path
from telebot import types  
from datetime import datetime, timedelta
from handlers.buy import *
from utils.admin_guard import is_admin  
from storage.db import get_connection  
from storage.repositories.bans import ban_user, unban_user, list_bans  
from storage.repositories.bin_bans import ban_bin, unban_bin, list_banned_bins
from storage.repositories.credits import get_credits, ensure_row  
from storage.repositories.codes import create_code    
from storage.repositories import gates  

ADMIN_STATES = {}  

# ================= GATES =================  
GATES = {  
    "stripe_auth": "Stripe Auth",  
    "shopify_charge": "Shopify Charge",  
    "braintree_auth": "Braintree Auth",  
    "stripe_charge": "Stripe Charge",  
    "paypal_donation": "Paypal Donation",  
}  

# ================= MAIN PANEL =================  
def render_main_panel(bot, chat_id, message_id=None, admin_name="Boss"):
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("👤 User Management", callback_data="ap:users"),
        types.InlineKeyboardButton("💰 Credits Control", callback_data="ap:credits"),
        types.InlineKeyboardButton("🛒 Buy Packages", callback_data="ap:buy"),
        types.InlineKeyboardButton("🚪 Gate Control", callback_data="ap:gates"),
        types.InlineKeyboardButton("🚫 BIN Management", callback_data="ap:bins"),
        types.InlineKeyboardButton("📢 Broadcast", callback_data="ap:broadcast"),
        types.InlineKeyboardButton("🗄 Database Manager", callback_data="ap:db_manager"),
    )

    text = f"""👑 Welcome My Boss \n<b>{admin_name}</b>
━━━━━━━━━━━━━━━    
🛠 Admin Control Panel
"""

    if message_id:
        bot.edit_message_text(
            text,
            chat_id,
            message_id,
            reply_markup=kb,
            parse_mode="HTML"
        )
    else:
        bot.send_message(
            chat_id,
            text,
            reply_markup=kb,
            parse_mode="HTML"
        )
  
# ================= USERS PANEL =================  
def render_users_panel(bot, chat_id, message_id):  
    kb = types.InlineKeyboardMarkup(row_width=1)  
    kb.add(  
        types.InlineKeyboardButton("🚫 Ban User", callback_data="user:ban"),  
        types.InlineKeyboardButton("✅ Unban User", callback_data="user:unban"),  
        types.InlineKeyboardButton("📋 Ban List", callback_data="user:list"),  
        types.InlineKeyboardButton("⬅ Back", callback_data="ap:back"),  
    )  
    bot.edit_message_text("👤 User Management", chat_id, message_id, reply_markup=kb)  
  
# ================= CREDITS PANEL =================  
def render_credits_panel(bot, chat_id, message_id):  
    kb = types.InlineKeyboardMarkup(row_width=1)  
    kb.add(  
        types.InlineKeyboardButton("➕ Add Credits", callback_data="credits:add"),  
        types.InlineKeyboardButton("➖ Take Credits", callback_data="credits:take"),  
        types.InlineKeyboardButton("♾ Unlimited User", callback_data="credits:unlimited"),  
        types.InlineKeyboardButton("💳 Check Credits", callback_data="credits:check"),  
        types.InlineKeyboardButton("💎 VIP Users", callback_data="credits:vip"),  
        types.InlineKeyboardButton("🎟 Create Code", callback_data="credits:code"),  
        types.InlineKeyboardButton("⬅ Back", callback_data="ap:back"),  
    )  
    bot.edit_message_text("💰 Credits Control", chat_id, message_id, reply_markup=kb)  

# ================= BINS PANEL =================  
def render_bins_panel(bot, chat_id, message_id):  
    kb = types.InlineKeyboardMarkup(row_width=1)  
    kb.add(  
        types.InlineKeyboardButton("🚫 Block BIN", callback_data="bin:block"),  
        types.InlineKeyboardButton("✅ Unblock BIN", callback_data="bin:unblock"),  
        types.InlineKeyboardButton("📋 Blocked BINs List", callback_data="bin:list"),  
        types.InlineKeyboardButton("⬅ Back", callback_data="ap:back"),  
    )  
    bot.edit_message_text("🚫 BIN Management", chat_id, message_id, reply_markup=kb)  
	
# ================= BUY PANEL =================    
def render_buy_panel(bot, chat_id, message_id):
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("➕ Add Package", callback_data="buy:add"),
        types.InlineKeyboardButton("📦 View Packages", callback_data="buy:list"),
        types.InlineKeyboardButton("⬅ Back", callback_data="ap:back"),
    )

    bot.edit_message_text(
        "🛒 Buy Packages Control",
        chat_id,
        message_id,
        reply_markup=kb
    )  

# ================= GATE PANEL =================  
def render_gate_panel(bot, chat_id, gate_key, message_id):  
    status = "ON ✅" if gates.is_gate_enabled(gate_key) else "OFF ❌"  
    limit = gates.get_limit(gate_key)  
    cost = gates.get_cost(gate_key)  
  
    kb = types.InlineKeyboardMarkup(row_width=1)  
    kb.add(  
        types.InlineKeyboardButton("🔄 Toggle ON / OFF", callback_data=f"gate:toggle:{gate_key}"),  
        types.InlineKeyboardButton("📦 Set Max Cards", callback_data=f"gate:limit:{gate_key}"),  
        types.InlineKeyboardButton("💰 Set Cost / Card", callback_data=f"gate:cost:{gate_key}"),  
        types.InlineKeyboardButton("⬅ Back", callback_data="ap:gates"),  
    )  
  
    bot.edit_message_text(  
        f"""🚪 <b>Gate Control</b>  
  
<b>Gate:</b> {GATES[gate_key]}  
<b>Status:</b> {status}  
<b>Max Cards:</b> {limit}  
<b>Cost / Card:</b> {cost}  
""",  
        chat_id,  
        message_id,  
        reply_markup=kb,  
        parse_mode="HTML"  
    )  
# ================= DATABASE Manger =================  
def render_db_manager_panel(bot, chat_id, message_id):
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("📁 Download Current Database", callback_data="download_db"),
        types.InlineKeyboardButton("📤 Upload New Database", callback_data="upload_db"),
        types.InlineKeyboardButton("⬅ Back", callback_data="ap:back")
    )
    bot.edit_message_text("🗄 Database Manager", chat_id, message_id, reply_markup=kb)
  
# ================= REGISTER =================  
def register_admin_panel(bot):

    # ===== SECURITY CHECK DECORATOR =====
    def admin_only(func):
        def wrapper(call_or_msg):
            user_id = call_or_msg.from_user.id if hasattr(call_or_msg, 'from_user') else call_or_msg.chat.id
            if not is_admin(user_id):
                if isinstance(call_or_msg, types.CallbackQuery):
                    bot.answer_callback_query(call_or_msg.id, "بطل بعبصه يا حبيبي فوق انت مش ادمن 🤨", show_alert=True)
                else:
                    bot.reply_to(call_or_msg, "هو انت ادمن يا عبيط علشان تستخدم الامر ده 😂")
                return
            return func(call_or_msg)
        return wrapper

    # ===== OPEN =====
    @bot.message_handler(commands=["admin"])
    @admin_only
    def admin_panel(message):
        admin_name = message.from_user.first_name or "Boss"
        render_main_panel(
            bot,
            message.chat.id,
            admin_name=admin_name
        )
  
    # ===== BACK =====  
    @bot.callback_query_handler(func=lambda c: c.data == "ap:back")
    @admin_only
    def back(c):
        ADMIN_STATES.pop(c.from_user.id, None)
        admin_name = c.from_user.first_name or "Boss"
        render_main_panel(
            bot,
            c.message.chat.id,
            c.message.message_id,
            admin_name=admin_name
        )
  
    # ===== USERS =====  
    @bot.callback_query_handler(func=lambda c: c.data == "ap:users")  
    @admin_only
    def users(c):  
        render_users_panel(bot, c.message.chat.id, c.message.message_id)  

    # ===== BINS ===== 

         
    @bot.callback_query_handler(func=lambda c: c.data == "ap:bins")  
    @admin_only
    def bins(c):  
        render_bins_panel(bot, c.message.chat.id, c.message.message_id)  

    @bot.callback_query_handler(func=lambda c: c.data in ("bin:block", "bin:unblock"))  
    @admin_only
    def bin_action(c):  
        ADMIN_STATES[c.from_user.id] = {"action": c.data}  
        bot.send_message(c.message.chat.id, "<b>Please send the BIN (6 digits) or upload a .txt / .json file for bulk action:</b>", parse_mode="HTML")  

    @bot.callback_query_handler(func=lambda c: c.data == "bin:list")  
    @admin_only
    def bin_list(c):  
        rows = list_banned_bins()  
        if not rows:  
            bot.send_message(c.message.chat.id, "No blocked BINs.")  
            return  
        
        txt = "🚫 Blocked BINs List:\n\n"  
        for bin_num, at in rows:  
            txt += f"• <code>{bin_num}</code> | {at}\n"  
        
        # تليجرام يسمح بـ 4096 حرف، سنستخدم 3800 للأمان
        if len(txt) > 3800:
            file_stream = io.BytesIO(txt.encode('utf-8'))
            file_stream.name = "blocked_bins.txt"
            bot.send_document(c.message.chat.id, file_stream, caption="📋 The list is too long, sent as a file.")
        else:
            bot.send_message(c.message.chat.id, txt, parse_mode="HTML")

    @bot.message_handler(content_types=['document', 'text'])
    @admin_only
    def handle_admin_inputs(message):
        uid = message.from_user.id
        if uid not in ADMIN_STATES:
            return
        
        state = ADMIN_STATES[uid]
        action = state.get("action")
        
        if action in ("bin:block", "bin:unblock"):
            bins_to_process = []
            
            # حالة الملف
            if message.document:
                file_info = bot.get_file(message.document.file_id)
                downloaded_file = bot.download_file(file_info.file_path)
                content = downloaded_file.decode('utf-8', errors='ignore')
            
                bins_to_process = []
            
                if message.document.file_name.endswith('.json'):
                    try:
                        data = json.loads(content)
                        # دعم القوائم والقواميس
                        if isinstance(data, list):
                            bins_to_process = [str(x)[:6] for x in data if str(x)[:6].isdigit()]
                        elif isinstance(data, dict):
                            bins_to_process = [str(v)[:6] for v in data.values() if str(v)[:6].isdigit()]
                    except Exception as e:
                        bot.reply_to(message, f"❌ Invalid JSON file: {e}")
                        return
                else:
                    # نصي أو كومبو (combo)
                    for line in content.splitlines():
                        line = line.strip()
                        if len(line) >= 6 and line[:6].isdigit():
                            bins_to_process.append(line[:6])
            
            # حالة النص العادي
            elif message.text:
                bins_to_process = [message.text.strip()[:6]]
            
            if not bins_to_process:
                bot.reply_to(message, "❌ No valid BINs found.")
                return
            
            success_count = 0
            for b in bins_to_process:
                if action == "bin:block":
                    ban_bin(b)
                    success_count += 1
                else:
                    unban_bin(b)
                    success_count += 1
            
            ADMIN_STATES.pop(uid)
            msg = "✅ Blocked" if action == "bin:block" else "✅ Unblocked"
            bot.send_message(message.chat.id, f"{msg} <b>{success_count}</b> BINs successfully.", parse_mode="HTML")



  
    @bot.callback_query_handler(func=lambda c: c.data in ("user:ban", "user:unban"))  
    @admin_only
    def user_action(c):  
        ADMIN_STATES[c.from_user.id] = {"action": c.data}  
        bot.send_message(c.message.chat.id, "Send user ID:")  
  
    @bot.callback_query_handler(func=lambda c: c.data == "user:list")  
    @admin_only
    def user_list(c):  
        rows = list_bans()  
        if not rows:  
            bot.send_message(c.message.chat.id, "No banned users.")  
            return  
        txt = "🚫 Banned users:\n\n"  
        for uid, reason, at in rows:  
            txt += f"- {uid} | {reason or 'no reason'} | {at}\n"  
        bot.send_message(c.message.chat.id, txt)  

    # ===== VIP USERS =====  
    @bot.callback_query_handler(func=lambda c: c.data == "credits:vip")  
    @admin_only
    def vip_users(c):  
        conn = get_connection()  
        cur = conn.cursor()  
        cur.execute("""
            SELECT 
                u.first_name,
                u.username,
                c.user_id,
                c.balance
            FROM credits c
            LEFT JOIN users u ON u.id = c.user_id
            WHERE c.balance > 0 OR c.balance = -1
        """)
        rows = cur.fetchall()
        conn.close()
        
        if not rows:
            bot.send_message(c.message.chat.id, "No Credited users.")
            return
    
        for name, username, uid, bal in rows:
            bot.send_message(
                c.message.chat.id,
                f"""
𝐀𝐜𝐜𝐨𝐮𝐧𝐭 𝐈𝐧𝐟𝐨
    
𝐍𝐚𝐦𝐞 : {name or 'NoName'}
𝐔𝐬𝐞𝐫𝐧𝐚𝐦𝐞 : @{username or 'NoUsername'}
𝐔𝐬𝐞𝐫 𝐈𝐃 : {uid}
𝐂𝐫𝐞𝐝𝐢𝐭𝐬 : {'Unlimited' if bal == -1 else bal}
    """
            )
      
    # ===== CREDITS =====  
    @bot.callback_query_handler(func=lambda c: c.data == "ap:credits")  
    @admin_only
    def credits(c):  
        render_credits_panel(bot, c.message.chat.id, c.message.message_id)  

    @bot.callback_query_handler(func=lambda c: c.data == "credits:unlimited")
    @admin_only
    def credits_unlimited(c):
        ADMIN_STATES[c.from_user.id] = {"action": "credits:unlimited"}
        bot.send_message(c.message.chat.id, "Send user ID:")
        
    @bot.callback_query_handler(func=lambda c: c.data == "credits:check")
    @admin_only
    def credits_check(c):
        ADMIN_STATES[c.from_user.id] = {"action": "credits:check"}
        bot.send_message(c.message.chat.id, "Send user ID:")
    
    @bot.callback_query_handler(
        func=lambda c: c.data in ("credits:add", "credits:take", "credits:code")
    )
    @admin_only
    def credits_action(c):
        ADMIN_STATES[c.from_user.id] = {"action": c.data}
        if c.data != "credits:code":
            bot.send_message(c.message.chat.id, "Send user ID:")
        else:
            bot.send_message(c.message.chat.id, "Send number of codes:")
  
    # ================= BUY PANEL & CALLBACKS (Corrected) =================    
    @bot.callback_query_handler(func=lambda c: c.data == "ap:buy")
    @admin_only
    def buy_panel(c):
        render_buy_panel(bot, c.message.chat.id, c.message.message_id)
    
    # ===== (هذا هو الجزء المضاف والمهم) =====
    @bot.callback_query_handler(func=lambda c: c.data == "buy:add")
    @admin_only
    def buy_add_prompt(c):
        ADMIN_STATES[c.from_user.id] = {"action": "buy:add_credits"}
        bot.send_message(c.message.chat.id, "💰 Send credits amount for the new package:")
    
    @bot.callback_query_handler(func=lambda c: c.data == "buy:list")
    @admin_only
    def buy_list(c):
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, credits, stars, bonus, active FROM buy_packages")
        rows = cur.fetchall()
        conn.close()
    
        if not rows:
            bot.answer_callback_query(c.id, "❌ No packages found")
            return
        
        bot.send_message(c.message.chat.id, "--- 📦 Available Packages ---")
        for pid, credits, stars, bonus, active in rows:
            status = "✅ Active" if active else "❌ Disabled"
            kb = types.InlineKeyboardMarkup(row_width=2)
            kb.add(
                types.InlineKeyboardButton("✏ Edit", callback_data=f"buy:edit:{pid}"),
                types.InlineKeyboardButton("🔁 Toggle", callback_data=f"buy:toggle:{pid}")
            )
            kb.add(types.InlineKeyboardButton("🗑 Delete", callback_data=f"buy:delete:{pid}"))
            bot.send_message(
                c.message.chat.id,
                f"📦 **Package #{pid}**\n\n💰 Credits: {credits}\n⭐ Stars: {stars}\n🎁 Bonus: {bonus}\n📌 Status: {status}",
                reply_markup=kb,
                parse_mode="Markdown"
            )
    
    @bot.callback_query_handler(func=lambda c: c.data.startswith("buy:toggle:"))
    @admin_only
    def buy_toggle(c):
        try:
            pid = int(c.data.split(":")[2])
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("UPDATE buy_packages SET active = 1 - active WHERE id = ?", (pid,))
            conn.commit()
            cur.execute("SELECT credits, stars, bonus, active FROM buy_packages WHERE id = ?", (pid,))
            row = cur.fetchone()
            conn.close()
            if not row:
                bot.answer_callback_query(c.id, "❌ Package not found.")
                return
            
            credits, stars, bonus, active = row
            status = "✅ Active" if active else "❌ Disabled"
            kb = types.InlineKeyboardMarkup(row_width=2)
            kb.add(
                types.InlineKeyboardButton("✏ Edit", callback_data=f"buy:edit:{pid}"),
                types.InlineKeyboardButton("🔁 Toggle", callback_data=f"buy:toggle:{pid}")
            )
            kb.add(types.InlineKeyboardButton("🗑 Delete", callback_data=f"buy:delete:{pid}"))
            
            bot.edit_message_text(
                f"📦 **Package #{pid}**\n\n💰 Credits: {credits}\n⭐ Stars: {stars}\n🎁 Bonus: {bonus}\n📌 Status: {status}",
                c.message.chat.id,
                c.message.message_id,
                reply_markup=kb,
                parse_mode="Markdown"
            )
            bot.answer_callback_query(c.id, "✅ Package status toggled.")
        except (ValueError, IndexError):
            bot.answer_callback_query(c.id, "❌ Invalid package ID.")
        except Exception as e:
            bot.answer_callback_query(c.id, f"❌ Error: {e}")
            if 'conn' in locals() and conn: conn.close()
    
    @bot.callback_query_handler(func=lambda c: c.data.startswith("buy:delete:"))
    @admin_only
    def buy_delete(c):
        try:
            pid = int(c.data.split(":")[2])
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("DELETE FROM buy_packages WHERE id = ?", (pid,))
            conn.commit()
            conn.close()
            bot.delete_message(c.message.chat.id, c.message.message_id)
            bot.answer_callback_query(c.id, "🗑 Package deleted.")
        except (ValueError, IndexError):
            bot.answer_callback_query(c.id, "❌ Invalid package ID.")
        except Exception as e:
            bot.answer_callback_query(c.id, f"❌ Error: {e}")
            if 'conn' in locals() and conn: conn.close()
    
    @bot.callback_query_handler(func=lambda c: c.data.startswith("buy:edit:"))
    @admin_only
    def buy_edit(c):
        try:
            pid = int(c.data.split(":")[2])
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("SELECT id FROM buy_packages WHERE id = ?", (pid,))
            if not cur.fetchone():
                bot.answer_callback_query(c.id, "❌ Package not found")
                conn.close()
                return
            conn.close()
        
            ADMIN_STATES[c.from_user.id] = {"action": "buy:edit_credits", "pid": pid}
            bot.send_message(c.message.chat.id, f"✏ Send new credits value for package #{pid}:")
        except (ValueError, IndexError):
            bot.answer_callback_query(c.id, "❌ Invalid package ID.")



    # ===== GATES =====  
    @bot.callback_query_handler(func=lambda c: c.data == "ap:gates")  
    @admin_only
    def gates_menu(c):  
        kb = types.InlineKeyboardMarkup(row_width=1)  
        for k, v in GATES.items():  
            kb.add(types.InlineKeyboardButton(v, callback_data=f"gate:open:{k}"))  
        kb.add(types.InlineKeyboardButton("⬅ Back", callback_data="ap:back"))  
        bot.edit_message_text("🚪 Gate Control", c.message.chat.id, c.message.message_id, reply_markup=kb)  
  
    @bot.callback_query_handler(func=lambda c: c.data.startswith("gate:open:"))  
    @admin_only
    def gate_open(c):  
        render_gate_panel(bot, c.message.chat.id, c.data.split(":")[2], c.message.message_id)  
  
    @bot.callback_query_handler(func=lambda c: c.data.startswith("gate:toggle:"))  
    @admin_only
    def gate_toggle(c):  
        gate = c.data.split(":")[2]  
        gates.set_enabled(gate, not gates.is_gate_enabled(gate))  
        render_gate_panel(bot, c.message.chat.id, gate, c.message.message_id)  
  
    @bot.callback_query_handler(func=lambda c: c.data.startswith("gate:limit:"))
    @admin_only
    def gate_limit(c):
        ADMIN_STATES[c.from_user.id] = {
            "action": "gate:limit", 
            "gate": c.data.split(":")[2],
            "message_id": c.message.message_id  # <-- هذا هو التعديل
        }
        bot.send_message(c.message.chat.id, "Send new max cards limit:")

    @bot.callback_query_handler(func=lambda c: c.data.startswith("gate:cost:"))
    @admin_only
    def gate_cost(c):
        ADMIN_STATES[c.from_user.id] = {
            "action": "gate:cost", 
            "gate": c.data.split(":")[2],
            "message_id": c.message.message_id  # <-- هذا هو التعديل
        }
        bot.send_message(c.message.chat.id, "Send new cost per card:")

  
    # ===== BROADCAST =====  
    @bot.callback_query_handler(func=lambda c: c.data == "ap:broadcast")  
    @admin_only
    def broadcast(c):  
        ADMIN_STATES[c.from_user.id] = {"action": "broadcast"}  
        bot.send_message(c.message.chat.id, "📢 Send broadcast message:")  


    # ================= DATABASE MANAGER =================
    
    @bot.callback_query_handler(func=lambda c: c.data == "ap:db_manager")
    @admin_only
    def db_manager_panel(c):
        render_db_manager_panel(bot, c.message.chat.id, c.message.message_id)
    
    
    @bot.callback_query_handler(func=lambda call: call.data in ["download_db", "upload_db"])
    @admin_only
    def handle_db_buttons(call):
    
        db_file = Path("storage/db.sqlite")
        db_file.parent.mkdir(parents=True, exist_ok=True)
    
        # ===== DOWNLOAD DATABASE =====
        if call.data == "download_db":
            try:
                # 🔥 تأكد أن أي اتصال مفتوح مغلق قبل النسخ
                try:
                    conn = get_connection()
                    conn.close()
                except:
                    pass
    
                with open(db_file, "rb") as f:
                    bot.send_document(call.from_user.id, f)
    
                bot.answer_callback_query(call.id, "✅ Database exported successfully")
    
            except Exception as e:
                bot.send_message(call.from_user.id, f"❌ Export failed: {e}")
    
        # ===== UPLOAD DATABASE =====
        elif call.data == "upload_db":
            msg = bot.send_message(call.from_user.id, "📤 Please send the new database file now:")
            bot.register_next_step_handler(msg, process_uploaded_db)
    
    
    def process_uploaded_db(message):
    
        if not hasattr(message, "document") or message.document is None:
            bot.send_message(message.chat.id, "❌ Please send a valid database file!")
            return
    
        db_path = Path("storage/db.sqlite")
        db_path.parent.mkdir(parents=True, exist_ok=True)
    
        try:
            # تحميل الملف الجديد
            file_info = bot.get_file(message.document.file_id)
            downloaded_file = bot.download_file(file_info.file_path)
    
            # 🔥 اغلق أي اتصال مفتوح
            try:
                conn = get_connection()
                conn.close()
            except:
                pass
    
            # 🔥 استبدال القاعدة بالكامل
            with open(db_path, "wb") as f:
                f.write(downloaded_file)
    
            bot.send_message(
                message.chat.id,
                "✅ Database replaced successfully!\n♻ Restarting bot..."
            )
    
            # 🔥 Restart كامل للبروسيس
            os.execv(sys.executable, [sys.executable] + sys.argv)
    
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ Error uploading DB: {e}")
        

  


    # ===== UNIFIED INPUT HANDLER (Final, Corrected Version) =====
    @bot.message_handler(func=lambda m: m.from_user.id in ADMIN_STATES)
    @admin_only
    def admin_input_handler(m):
        state = ADMIN_STATES.get(m.from_user.id)
        if not state: return
        action = state.get("action")
        
        try:
            # ===== BROADCAST (Corrected) =====
            if action == "broadcast":
                ADMIN_STATES.pop(m.from_user.id, None) # Remove state first
                conn = get_connection()
                cur = conn.cursor()
                cur.execute("SELECT id FROM users")
                users_list = cur.fetchall()
                conn.close()
                
                if not users_list:
                    bot.send_message(m.chat.id, "No users to broadcast to.")
                    return

                success, fail = 0, 0
                status_msg = bot.send_message(m.chat.id, f"🚀 Starting broadcast to {len(users_list)} users...")
                
                for (uid,) in users_list:
                    try:
                        bot.copy_message(uid, m.chat.id, m.message_id)
                        success += 1
                    except Exception as e:
                        fail += 1
                        print(f"Failed to send broadcast to {uid}: {e}")
                
                bot.edit_message_text(
                    f"""📢 <b>Broadcast Finished!</b>
━━━━━━━━━━━━━━━
✅ <b>Success:</b> {success}
❌ <b>Failed:</b> {fail}
👥 <b>Total:</b> {len(users_list)}""",
                    m.chat.id,
                    status_msg.message_id,
                    parse_mode="HTML"
                )
                return # End function here

            # ===== USER MANAGEMENT =====
            elif action == "user:ban":
                user_id = int(m.text); ban_user(user_id, reason="Banned by admin.")
                bot.send_message(m.chat.id, f"✅ User {user_id} has been banned.")
            
            elif action == "user:unban":
                user_id = int(m.text); unban_user(user_id)
                bot.send_message(m.chat.id, f"✅ User {user_id} has been unbanned.")

            # ===== CREDITS MANAGEMENT =====
            elif action == "credits:add":
                user_id = int(m.text); ensure_row(user_id)
                ADMIN_STATES[m.from_user.id] = {"action": "credits:add_amount", "target": user_id}
                bot.send_message(m.chat.id, f"Send amount to add to user {user_id}:")
                return 

            elif action == "credits:add_amount":
                amount = int(m.text); user_id = state["target"]
                conn = get_connection(); cur = conn.cursor()
                cur.execute("UPDATE credits SET balance = balance + ? WHERE user_id = ?", (amount, user_id)); conn.commit(); conn.close()
                bot.send_message(m.chat.id, f"✅ Added {amount} credits to user {user_id}.")

            elif action == "credits:take":
                user_id = int(m.text); ensure_row(user_id)
                ADMIN_STATES[m.from_user.id] = {"action": "credits:take_amount", "target": user_id}
                bot.send_message(m.chat.id, f"Send amount to take from user {user_id}:")
                return

            elif action == "credits:take_amount":
                amount = int(m.text); user_id = state["target"]
                conn = get_connection(); cur = conn.cursor()
                cur.execute("UPDATE credits SET balance = balance - ? WHERE user_id = ?", (amount, user_id)); conn.commit(); conn.close()
                bot.send_message(m.chat.id, f"✅ Took {amount} credits from user {user_id}.")

            elif action == "credits:unlimited":
                user_id = int(m.text); ensure_row(user_id)
                conn = get_connection(); cur = conn.cursor()
                cur.execute("UPDATE credits SET balance = -1 WHERE user_id = ?", (user_id,)); conn.commit(); conn.close()
                bot.send_message(m.chat.id, f"💳 User {user_id} now has unlimited credits.")

            elif action == "credits:check":
                user_id = int(m.text)
                balance = get_credits(user_id)
                bot.send_message(m.chat.id, f"💳 User {user_id} Balance: {'Unlimited' if balance == -1 else balance}")

            # ===== CODE GENERATION (New Style) =====
            elif action == "credits:code":
                ADMIN_STATES[m.from_user.id] = {"action": "code:credits", "count": int(m.text)}
                bot.send_message(m.chat.id, "Send credits per code:")
                return

            elif action == "code:credits":
                ADMIN_STATES[m.from_user.id].update({"action": "code:max_uses", "credits": int(m.text)})
                bot.send_message(m.chat.id, "Send max uses per code:")
                return

            elif action == "code:max_uses":
                max_uses = int(m.text)
                count = state["count"]
                credits_val = state["credits"]
                codes = [create_code(credits=credits_val, max_uses=max_uses) for _ in range(count)]
                
                if count > 1:
                    txt = "\n".join(f"<code>{c}</code>" for c in codes)
                    msg = f"""⟡⟡⟡⟡⟡⟡⟡⟡⟡⟡
💎 𝗩𝗜𝗣 𝗖𝗢𝗗𝗘𝗦 𝗚𝗘𝗡𝗘𝗥𝗔𝗧𝗘𝗗
⟡⟡⟡⟡⟡⟡⟡⟡⟡⟡

💰 Credits / Code -> {credits_val}
👥 Max Uses -> {max_uses}
📦 Total Codes -> {count}

━━━━━━━━━━━━━━━━━━
{txt}
━━━━━━━━━━━━━━━━━━

📌 You can use any code with /redeem"""
                else:
                    msg = f"""━━━━━━━━━━━━━━━━━━
🎟 𝗖𝗢𝗗𝗘 𝗖𝗥𝗘𝗔𝗧𝗘𝗗
━━━━━━━━━━━━━━━━━━

🔑 Code -> <code>{codes[0]}</code>
💰 Credits -> {credits_val}
👥 Max Uses -> {max_uses}

📌 You can use this code with /redeem
━━━━━━━━━━━━━━━━━━"""
                
                bot.send_message(m.chat.id, msg, parse_mode="HTML")


            # ===== GATE MANAGEMENT =====
            elif action == "gate:limit":
                gate_key = state["gate"]; new_limit = int(m.text)
                gates.set_limit(gate_key, new_limit)
                bot.send_message(m.chat.id, f"✅ Limit for {GATES[gate_key]} updated.")
                render_gate_panel(bot, m.chat.id, gate_key, state["message_id"])

            elif action == "gate:cost":
                gate_key = state["gate"]; new_cost = int(m.text)
                gates.set_cost(gate_key, new_cost)
                bot.send_message(m.chat.id, f"✅ Cost for {GATES[gate_key]} updated.")
                render_gate_panel(bot, m.chat.id, gate_key, state["message_id"])

            # ===== BUY PACKAGE MANAGEMENT =====
            elif action == "buy:add_credits":
                credits = int(m.text)
                ADMIN_STATES[m.from_user.id] = {"action": "buy:add_stars", "credits": credits}
                bot.send_message(m.chat.id, "⭐ Send stars amount:")
                return

            elif action == "buy:add_stars":
                stars = int(m.text)
                ADMIN_STATES[m.from_user.id].update({"action": "buy:add_bonus", "stars": stars})
                bot.send_message(m.chat.id, "🎁 Send bonus amount:")
                return

            elif action == "buy:add_bonus":
                bonus = int(m.text)
                conn = get_connection(); cur = conn.cursor()
                cur.execute("INSERT INTO buy_packages (credits, stars, bonus, active) VALUES (?, ?, ?, 1)", (state["credits"], state["stars"], bonus))
                conn.commit(); conn.close()
                bot.send_message(m.chat.id, "✅ Package added successfully.")

            elif action == "buy:edit_credits":
                credits = int(m.text)
                ADMIN_STATES[m.from_user.id].update({"action": "buy:edit_stars", "credits": credits})
                bot.send_message(m.chat.id, "⭐ Send new stars value:")
                return

            elif action == "buy:edit_stars":
                stars = int(m.text)
                ADMIN_STATES[m.from_user.id].update({"action": "buy:edit_bonus", "stars": stars})
                bot.send_message(m.chat.id, "🎁 Send new bonus value:")
                return

            elif action == "buy:edit_bonus":
                bonus = int(m.text)
                conn = get_connection(); cur = conn.cursor()
                cur.execute("UPDATE buy_packages SET credits = ?, stars = ?, bonus = ? WHERE id = ?", (state["credits"], state["stars"], bonus, state["pid"]))
                conn.commit(); conn.close()
                bot.send_message(m.chat.id, "✅ Package updated successfully.")

            # Clean up state after action is done
            if m.from_user.id in ADMIN_STATES:
                ADMIN_STATES.pop(m.from_user.id, None)

        except Exception as e:
            bot.send_message(m.chat.id, f"❌ An error occurred: {str(e)}")
            ADMIN_STATES.pop(m.from_user.id, None)
