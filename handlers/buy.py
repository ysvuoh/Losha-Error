from telebot import types
from security.channel_guard import is_channel_subscribed, send_channel_prompt
from config.settings import ADMINS
from storage.db import get_connection
from storage.repositories.credits import ensure_row
from storage.repositories.bans import is_banned

# ======================
# HELPERS
# ======================

def get_packages():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, credits, stars, bonus
        FROM buy_packages
        WHERE active = 1
        ORDER BY credits ASC
    """)
    rows = cur.fetchall()
    conn.close()
    return rows


def create_order(user_id, credits, stars, bonus):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO buy_orders (user_id, credits, stars, bonus, status)
        VALUES (?, ?, ?, ?, 'pending')
    """, (user_id, credits, stars, bonus))
    order_id = cur.lastrowid
    conn.commit()
    conn.close()
    return order_id


# ======================
# REGISTER
# ======================

def register_buy(bot):

    # ======================
    # /buy
    # ======================
    @bot.message_handler(commands=["buy"])
    def buy(message):
        uid = message.from_user.id
        user_id = message.from_user.id
        user_name = message.from_user.first_name
        name = message.from_user.first_name or "Hidden"
        username = message.from_user.username
        if message.chat.type != "private":
            bot.reply_to(message, "❌ Use /buy in private chat")
            return
            
        if is_banned(uid):
            bot.send_message(
                message.chat.id,
                "<b>🚫 YOU ARE BANNED FROM USING THIS BOT</b>",
                parse_mode="HTML"
            )
            return            
            

            
        packages = get_packages()
        if not packages:
            bot.send_message(message.chat.id, "❌ No packages available contact with @I_EOR or @H_Eor to buy credits.")
            return

        kb = types.InlineKeyboardMarkup(row_width=1)

        for pid, credits, stars, bonus in packages:
            if bonus > 0:
                txt = f"⭐ {credits} Credits (+{bonus} Bonus)"
            else:
                txt = f"⭐ {credits} Credits"

            kb.add(
                types.InlineKeyboardButton(
                    txt,
                    callback_data=f"buy:pkg:{pid}"
                )
            )

        bot.send_message(
            message.chat.id,
            "<b>🛒 Choose Credits Package</b>",
            reply_markup=kb,
            parse_mode="HTML"
        )

    # ======================
    # PACKAGE SELECT
    # ======================
    @bot.callback_query_handler(func=lambda c: c.data.startswith("buy:pkg:"))
    def choose_package(c):
        bot.answer_callback_query(c.id)

        if c.message.chat.type != "private":
            bot.send_message(
                c.from_user.id,
                "❌ Please use /buy in private chat"
            )
            return

        pkg_id = int(c.data.split(":")[2])

        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT credits, stars, bonus
            FROM buy_packages
            WHERE id = ? AND active = 1
        """, (pkg_id,))
        row = cur.fetchone()
        conn.close()

        if not row:
            bot.send_message(c.from_user.id, "❌ Package not found")
            return

        credits, stars, bonus = row

        order_id = create_order(
            c.from_user.id,
            credits,
            stars,
            bonus
        )

        payload = f"order_{order_id}"

        send_invoice(
            bot=bot,
            chat_id=c.from_user.id,
            stars=stars,
            credits=credits,
            bonus=bonus,
            payload=payload
        )

    # ======================
    # SEND INVOICE
    # ======================
    def send_invoice(bot, chat_id, stars, credits, bonus, payload):
        prices = [
            types.LabeledPrice(
                label=f"{credits} Credits",
                amount=int(stars)
            )
        ]

        if bonus > 0:
            description = f"{credits} Credits\n🎁 Bonus: {bonus}"
        else:
            description = f"{credits} Credits"

        bot.send_invoice(
            chat_id=chat_id,
            title="Buy Credits",
            description=description,
            invoice_payload=payload,
            provider_token="",  # Telegram Stars
            currency="XTR",
            prices=prices,
            start_parameter="buycredits"
        )

    # ======================
    # PRE CHECKOUT
    # ======================
    @bot.pre_checkout_query_handler(func=lambda q: True)
    def pre_checkout(q):
        bot.answer_pre_checkout_query(q.id, ok=True)

    # ======================
    # PAYMENT SUCCESS
    # ======================
    @bot.message_handler(content_types=["successful_payment"])
    def successful_payment(message):
        payload = message.successful_payment.invoice_payload
        order_id = int(payload.split("_")[1])

        bot.send_message(
            message.chat.id,
            "<b>⏳ Payment received\nWaiting admin confirmation</b>",
            parse_mode="HTML"
        )

        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT user_id, credits, stars, bonus
            FROM buy_orders
            WHERE id = ? AND status = 'pending'
        """, (order_id,))
        row = cur.fetchone()
        conn.close()

        if not row:
            return

        user_id, credits, stars, bonus = row

        for admin in ADMINS:
            kb = types.InlineKeyboardMarkup()
            kb.add(
                types.InlineKeyboardButton(
                    "✅ Confirm",
                    callback_data=f"buy:confirm:{order_id}"
                ),
                types.InlineKeyboardButton(
                    "❌ Reject",
                    callback_data=f"buy:reject:{order_id}"
                )
            )

            bot.send_message(
                admin,
                f"""<b>💳 New Buy Order</b>

🆔 Order ID: <code>{order_id}</code>
👤 User ID: <code>{user_id}</code>
💰 Credits: {credits}
🎁 Bonus: {bonus}

Status: Pending
""",
                reply_markup=kb,
                parse_mode="HTML"
            )

    # ======================
    # ADMIN CONFIRM
    # ======================
    @bot.callback_query_handler(func=lambda c: c.data.startswith("buy:confirm:"))
    def confirm_buy(c):
        if c.from_user.id not in ADMINS:
            return

        order_id = int(c.data.split(":")[2])

        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT user_id, credits, bonus
            FROM buy_orders
            WHERE id = ? AND status = 'pending'
        """, (order_id,))
        row = cur.fetchone()

        if not row:
            bot.answer_callback_query(c.id, "Already processed")
            conn.close()
            return

        user_id, credits, bonus = row

        ensure_row(user_id)

        cur.execute(
            "UPDATE credits SET balance = balance + ? WHERE user_id = ?",
            (credits + bonus, user_id)
        )
        cur.execute(
            "UPDATE buy_orders SET status = 'approved' WHERE id = ?",
            (order_id,)
        )

        conn.commit()
        conn.close()

        bot.edit_message_text(
            c.message.text + "\n\n<b>✅ APPROVED</b>",
            c.message.chat.id,
            c.message.message_id,
            parse_mode="HTML"
        )

        bot.send_message(
            user_id,
            f"""<b>✅ Payment Approved</b>

💰 Credits Added: {credits}
🎁 Bonus: {bonus}
""",
            parse_mode="HTML"
        )

    # ======================
    # ADMIN REJECT
    # ======================
    @bot.callback_query_handler(func=lambda c: c.data.startswith("buy:reject:"))
    def reject_buy(c):
        if c.from_user.id not in ADMINS:
            return

        order_id = int(c.data.split(":")[2])

        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "UPDATE buy_orders SET status = 'rejected' WHERE id = ?",
            (order_id,)
        )
        conn.commit()
        conn.close()

        bot.edit_message_text(
            c.message.text + "\n\n<b>❌ REJECTED</b>",
            c.message.chat.id,
            c.message.message_id,
            parse_mode="HTML"
        )
