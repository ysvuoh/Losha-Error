from telebot import types  
from datetime import datetime, timedelta

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
        bot.send_message(c.message.chat.id, "Send BIN (6 digits):")  

    @bot.callback_query_handler(func=lambda c: c.data == "bin:list")  
    @admin_only
    def bin_list(c):  
        rows = list_banned_bins()  
        if not rows:  
            bot.send_message(c.message.chat.id, "No blocked BINs.")  
            return  
        txt = "🚫 Blocked BINs:\n\n"  
        for bin_num, at in rows:  
            txt += f"- <code>{bin_num}</code> | {at}\n"  
        bot.send_message(c.message.chat.id, txt, parse_mode="HTML")  
  
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
  
    # ===== BUY =====  
    @bot.callback_query_handler(func=lambda c: c.data == "ap:buy")
    @admin_only
    def buy_panel(c):
        render_buy_panel(bot, c.message.chat.id, c.message.message_id)

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
    
        for pid, credits, stars, bonus, active in rows:
            status = "✅ Active" if active else "❌ Disabled"
    
            kb = types.InlineKeyboardMarkup(row_width=2)
            kb.add(
                types.InlineKeyboardButton("✏ Edit", callback_data=f"buy:edit:{pid}"),
                types.InlineKeyboardButton("🔁 Toggle", callback_data=f"buy:toggle:{pid}")
            )
            kb.add(
                types.InlineKeyboardButton("🗑 Delete", callback_data=f"buy:delete:{pid}")
            )
    
            bot.send_message(
                c.message.chat.id,
                f"""📦 Package #{pid}
    
💰 Credits: {credits}
⭐ Stars: {stars}
🎁 Bonus: {bonus}
📌 Status: {status}
    """,
                reply_markup=kb
            )

    @bot.callback_query_handler(func=lambda c: c.data.startswith("buy:toggle:"))
    @admin_only
    def buy_toggle(c):
        pid = int(c.data.split(":")[2])
    
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("UPDATE buy_packages SET active = 1 - active WHERE id = ?", (pid,))
        cur.execute("SELECT credits, stars, bonus, active FROM buy_packages WHERE id = ?", (pid,))
        row = cur.fetchone()
        conn.commit()
        conn.close()
    
        if not row:
            bot.answer_callback_query(c.id, "❌ Package not found")
            return
    
        credits, stars, bonus, active = row
        status = "✅ Active" if active else "❌ Disabled"
    
        kb = types.InlineKeyboardMarkup(row_width=2)
        kb.add(
            types.InlineKeyboardButton("✏ Edit", callback_data=f"buy:edit:{pid}"),
            types.InlineKeyboardButton("🔁 Toggle", callback_data=f"buy:toggle:{pid}")
        )
        kb.add(
            types.InlineKeyboardButton("🗑 Delete", callback_data=f"buy:delete:{pid}")
        )
    
        bot.edit_message_text(
            f"""📦 Package #{pid}
    
💰 Credits: {credits}
⭐ Stars: {stars}
🎁 Bonus: {bonus}
📌 Status: {status}
    """,
            c.message.chat.id,
            c.message.message_id,
            reply_markup=kb
        )
        bot.answer_callback_query(c.id, "✅ Package enabled" if active else "⛔ Package disabled")

    @bot.callback_query_handler(func=lambda c: c.data.startswith("buy:delete:"))
    @admin_only
    def buy_delete(c):
        pid = int(c.data.split(":")[2])
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM buy_packages WHERE id = ?", (pid,))
        conn.commit()
        conn.close()
        bot.delete_message(c.message.chat.id, c.message.message_id)
        bot.answer_callback_query(c.id, "🗑 Package deleted")

    @bot.callback_query_handler(func=lambda c: c.data.startswith("buy:edit:"))
    @admin_only
    def buy_edit(c):
        pid = int(c.data.split(":")[2])
        ADMIN_STATES[c.from_user.id] = {"action": "buy:edit_credits", "pid": pid}
        bot.send_message(c.message.chat.id, "✏ Send new credits value:")

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
        ADMIN_STATES[c.from_user.id] = {"action": "gate:limit", "gate": c.data.split(":")[2]}  
        bot.send_message(c.message.chat.id, "Send new max cards limit:")  
  
    @bot.callback_query_handler(func=lambda c: c.data.startswith("gate:cost:"))  
    @admin_only
    def gate_cost(c):  
        ADMIN_STATES[c.from_user.id] = {"action": "gate:cost", "gate": c.data.split(":")[2]}  
        bot.send_message(c.message.chat.id, "Send new cost per card:")  
  
    # ===== BROADCAST =====  
    @bot.callback_query_handler(func=lambda c: c.data == "ap:broadcast")  
    @admin_only
    def broadcast(c):  
        ADMIN_STATES[c.from_user.id] = {"action": "broadcast"}  
        bot.send_message(c.message.chat.id, "📢 Send broadcast message:")  
         
    # ===== INPUT HANDLER =====  
    @bot.message_handler(func=lambda m: m.from_user.id in ADMIN_STATES)
    @admin_only
    def admin_input(m):
        state = ADMIN_STATES.get(m.from_user.id)
        if not state: return
        action = state["action"]
    
        try:
            # ===== BROADCAST EXECUTION =====
            if action == "broadcast":
                ADMIN_STATES.pop(m.from_user.id, None)
                conn = get_connection()
                cur = conn.cursor()
                cur.execute("SELECT id FROM users")
                users_list = cur.fetchall()
                conn.close()
                
                success, fail = 0, 0
                status_msg = bot.send_message(m.chat.id, f"🚀 Starting broadcast to {len(users_list)} users...")
                
                for (uid,) in users_list:
                    try:
                        bot.copy_message(uid, m.chat.id, m.message_id)
                        success += 1
                    except:
                        fail += 1
                
                bot.edit_message_text(
                    f"""📢 <b>Broadcast Finished!</b>
━━━━━━━━━━━━━━━
✅ <b>Success:</b> {success}
❌ <b>Failed:</b> {fail}
👥 <b>Total:</b> {len(users_list)}
━━━━━━━━━━━━━━━
Done My Boss! 👑""",
                    m.chat.id,
                    status_msg.message_id,
                    parse_mode="HTML"
                )
                return

            # ===== USER BAN =====  
            elif action == "user:ban":
                target_id = int(m.text)
                ban_user(target_id, reason="Admin decision")
                try:
                    user = bot.get_chat(target_id)
                    name, username = user.first_name or "Unknown", f"@{user.username}" if user.username else "NoUsername"
                except:
                    name, username = "Unknown", "Unknown"
                
                bot.send_message(m.chat.id, f"✅ User Banned\nName: {name}\nID: {target_id}")
                ADMIN_STATES.pop(m.from_user.id, None)
                return
  
            elif action == "user:unban":
                target_id = int(m.text)
                unban_user(target_id)
                bot.send_message(m.chat.id, f"✅ User Unbanned: {target_id}")
                ADMIN_STATES.pop(m.from_user.id, None)
                return
  
            # ===== CREDITS =====  
            elif action == "credits:add":  
                ensure_row(int(m.text))  
                ADMIN_STATES[m.from_user.id] = {"action": "credits:add_amount", "target": int(m.text)}  
                bot.send_message(m.chat.id, "Send amount:")  
                return  
  
            elif action == "credits:add_amount":  
                conn = get_connection()  
                cur = conn.cursor()  
                cur.execute("UPDATE credits SET balance = balance + ? WHERE user_id = ?", (int(m.text), state["target"]))  
                conn.commit(); conn.close()  
                bot.send_message(m.chat.id, "✅ Credits added.")
                ADMIN_STATES.pop(m.from_user.id, None)
                return
  
            elif action == "credits:take":  
                ensure_row(int(m.text))  
                ADMIN_STATES[m.from_user.id] = {"action": "credits:take_amount", "target": int(m.text)}  
                bot.send_message(m.chat.id, "Send amount:")  
                return  
  
            elif action == "credits:take_amount":  
                conn = get_connection()  
                cur = conn.cursor()  
                cur.execute("UPDATE credits SET balance = balance - ? WHERE user_id = ?", (int(m.text), state["target"]))  
                conn.commit(); conn.close()  
                bot.send_message(m.chat.id, "✅ Credits taken.")
                ADMIN_STATES.pop(m.from_user.id, None)
                return

            elif action == "credits:unlimited":
                uid = int(m.text)
                conn = get_connection(); cur = conn.cursor()
                cur.execute("UPDATE credits SET balance = -1 WHERE user_id = ?", (uid,))
                conn.commit(); conn.close()
                bot.send_message(m.chat.id, f"💳 User {uid} now has Unlimited credits")
                ADMIN_STATES.pop(m.from_user.id, None)
                return

            elif action == "credits:check":
                uid = int(m.text)
                bal = get_credits(uid)
                bot.send_message(m.chat.id, f"💳 User {uid} Balance: {'Unlimited' if bal == -1 else bal}")
                ADMIN_STATES.pop(m.from_user.id, None)
                return

            # ===== CODES =====
            elif action == "credits:code":
                ADMIN_STATES[m.from_user.id] = {"action": "code:credits", "count": int(m.text)}
                bot.send_message(m.chat.id, "Send credits per code:")
                return

            elif action == "code:credits":
                ADMIN_STATES[m.from_user.id] = {"action": "code:max_uses", "count": state["count"], "credits": int(m.text)}
                bot.send_message(m.chat.id, "Send max uses per code:")
                return

            elif action == "code:max_uses":
                max_uses = int(m.text)
                count = state["count"]
                credits_val = state["credits"]
                codes = []
                for _ in range(count):
                    c = create_code(credits=credits_val, max_uses=max_uses)
                    codes.append(c)
                
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
                ADMIN_STATES.pop(m.from_user.id, None)
                return

            # ===== BUY PACKAGES =====
            elif action == "buy:add_credits":
                ADMIN_STATES[m.from_user.id] = {"action": "buy:add_stars", "credits": int(m.text)}
                bot.send_message(m.chat.id, "⭐ Send stars amount:")
                return

            elif action == "buy:add_stars":
                ADMIN_STATES[m.from_user.id] = {"action": "buy:add_bonus", "credits": state["credits"], "stars": int(m.text)}
                bot.send_message(m.chat.id, "🎁 Send bonus amount:")
                return

            elif action == "buy:add_bonus":
                conn = get_connection(); cur = conn.cursor()
                cur.execute("INSERT INTO buy_packages (credits, stars, bonus, active) VALUES (?, ?, ?, 1)", (state["credits"], state["stars"], int(m.text)))
                conn.commit(); conn.close()
                bot.send_message(m.chat.id, "✅ Package added successfully")
                ADMIN_STATES.pop(m.from_user.id, None)
                return

            elif action == "buy:edit_credits":
                ADMIN_STATES[m.from_user.id] = {"action": "buy:edit_stars", "pid": state["pid"], "credits": int(m.text)}
                bot.send_message(m.chat.id, "⭐ Send new stars value:")
                return
            
            elif action == "buy:edit_stars":
                ADMIN_STATES[m.from_user.id] = {"action": "buy:edit_bonus", "pid": state["pid"], "credits": state["credits"], "stars": int(m.text)}
                bot.send_message(m.chat.id, "🎁 Send new bonus:")
                return
            
            elif action == "buy:edit_bonus":
                conn = get_connection(); cur = conn.cursor()
                cur.execute("UPDATE buy_packages SET credits = ?, stars = ?, bonus = ? WHERE id = ?", (state["credits"], state["stars"], int(m.text), state["pid"]))
                conn.commit(); conn.close()
                bot.send_message(m.chat.id, "✅ Package updated successfully")
                ADMIN_STATES.pop(m.from_user.id, None)
                return

            # ===== GATES =====
            elif action == "gate:limit":
                gates.set_limit(state["gate"], int(m.text))
                bot.send_message(m.chat.id, "✅ Limit updated")
                ADMIN_STATES.pop(m.from_user.id, None)
                return

            elif action == "gate:cost":
                gates.set_cost(state["gate"], int(m.text))
                bot.send_message(m.chat.id, "✅ Cost updated")
                ADMIN_STATES.pop(m.from_user.id, None)
                return

            # ===== BINS =====
            elif action == "bin:block":
                bin_num = str(m.text).strip()[:6]
                if not bin_num.isdigit() or len(bin_num) < 6:
                    bot.send_message(m.chat.id, "❌ Invalid BIN. Send 6 digits.")
                    return
                ban_bin(bin_num)
                bot.send_message(m.chat.id, f"✅ BIN <code>{bin_num}</code> blocked.", parse_mode="HTML")
                ADMIN_STATES.pop(m.from_user.id, None)
                return

            elif action == "bin:unblock":
                bin_num = str(m.text).strip()[:6]
                unban_bin(bin_num)
                bot.send_message(m.chat.id, f"✅ BIN <code>{bin_num}</code> unblocked.", parse_mode="HTML")
                ADMIN_STATES.pop(m.from_user.id, None)
                return

        except Exception as e:
            bot.send_message(m.chat.id, f"❌ Error: {str(e)}")
            ADMIN_STATES.pop(m.from_user.id, None)
