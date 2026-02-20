from telebot import types
from storage.db import get_connection
from storage.repositories.credits import ensure_row, get_credits
from storage.repositories.bans import is_banned

def register_redeem(bot):

    @bot.message_handler(commands=["redeem"])
    def redeem_code(message):
        user = message.from_user
        user_id = user.id

        if is_banned(user_id):
            bot.send_message(
                message.chat.id,
                "🚫 You are banned from using this bot."
            )
            return

        try:
            parts = message.text.split()
            if len(parts) != 2:
                bot.reply_to(message, "❌ Usage: /redeem CODE")
                return

            code = parts[1].strip().upper()

            conn = get_connection()
            cur = conn.cursor()

            # تحقق إن المستخدم ما استخدمش الكود قبل كده
            cur.execute(
                "SELECT 1 FROM code_redeems WHERE code = ? AND user_id = ?",
                (code, user_id)
            )
            if cur.fetchone():
                conn.close()
                bot.reply_to(message, "❌ You already redeemed this code.")
                return

            # جلب بيانات الكود
            cur.execute(
                """
                SELECT credits, vip_minutes, max_uses, used_count
                FROM codes
                WHERE code = ?
                """,
                (code,)
            )
            row = cur.fetchone()
            if not row:
                conn.close()
                bot.reply_to(message, "❌ Invalid or expired code.")
                return

            credits, vip_minutes, max_uses, used_count = row

            if used_count >= max_uses:
                conn.close()
                bot.reply_to(message, "❌ This code has reached its maximum uses.")
                return

            # تجهيز المستخدم
            ensure_row(user_id)
            balance = get_credits(user_id)

            # إضافة Credits إذا موجود
            if credits and credits > 0 and balance != -1:
                cur.execute(
                    "UPDATE credits SET balance = balance + ? WHERE user_id = ?",
                    (credits, user_id)
                )

            # إضافة VIP إذا موجود
            vip_duration_text = None
            if vip_minutes and vip_minutes > 0:
                # التراكُم مع الوقت الحالي
                cur.execute("SELECT expires_at FROM vip_status WHERE user_id = ?", (user_id,))
                row = cur.fetchone()
                if row and row[0]:
                    # المستخدم عنده VIP قائم
                    cur.execute("""
                        UPDATE vip_status
                        SET expires_at = datetime(?, '+' || ? || ' minutes')
                        WHERE user_id = ?
                    """, (row[0], vip_minutes, user_id))
                    conn.commit()
                    cur.execute("SELECT expires_at FROM vip_status WHERE user_id = ?", (user_id,))
                    expires_at = cur.fetchone()[0]
                else:
                    # لا يوجد VIP سابق
                    cur.execute("""
                        INSERT INTO vip_status (user_id, expires_at)
                        VALUES (?, datetime('now', ? || ' minutes'))
                    """, (user_id, vip_minutes))
                    conn.commit()
                    cur.execute("SELECT expires_at FROM vip_status WHERE user_id = ?", (user_id,))
                    expires_at = cur.fetchone()[0]

                # حساب الوقت المتبقي بالدقائق
                cur.execute("SELECT (strftime('%s', ?) - strftime('%s','now'))/60", (expires_at,))
                remaining_minutes = int(cur.fetchone()[0])
                
                if remaining_minutes >= 1440 and remaining_minutes % 1440 == 0:
                    days = remaining_minutes // 1440
                    vip_duration_text = f"{days} day{'s' if days > 1 else ''}"
                elif remaining_minutes >= 60 and remaining_minutes % 60 == 0:
                    hours = remaining_minutes // 60
                    vip_duration_text = f"{hours} hour{'s' if hours > 1 else ''}"
                else:
                    vip_duration_text = f"{remaining_minutes} minute{'s' if remaining_minutes > 1 else ''}"

            # تحديث استخدام الكود
            cur.execute(
                "UPDATE codes SET used_count = used_count + 1 WHERE code = ?",
                (code,)
            )

            # تسجيل إن المستخدم استخدم الكود
            cur.execute(
                "INSERT INTO code_redeems (code, user_id) VALUES (?, ?)",
                (code, user_id)
            )

            conn.commit()
            new_balance = get_credits(user_id)
            conn.close()

            # إرسال رسالة مخصصة حسب نوع الكود
            if vip_duration_text:
                msg = f"""
━━━━━━━━━━━━━━━━━━
💎 <b>VIP ACTIVATED!</b>
━━━━━━━━━━━━━━━━━━

👤 User : {user.first_name}
🆔 ID : {user_id}
⏱ Duration Remaining : {vip_duration_text}
✨ Enjoy exclusive VIP features!
━━━━━━━━━━━━━━━━━━
"""
            else:
                msg = f"""
━━━━━━━━━━━━━━━━━━
✅ <b>CODE REDEEMED</b>
━━━━━━━━━━━━━━━━━━

🎟 Code -> <code>{code}</code>
💰 Credits -> +{credits if credits else 0}
💳 Balance -> {'Unlimited' if new_balance == -1 else new_balance}

✨ Enjoy using all bot commands
━━━━━━━━━━━━━━━━━━
"""

            bot.send_message(message.chat.id, msg, parse_mode="HTML")

        except Exception as e:
            print(f"Error redeeming code: {e}")
            bot.reply_to(message, "❌ Error redeeming the code.")