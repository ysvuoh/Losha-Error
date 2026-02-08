# handlers/me.py
from storage.repositories.credits import ensure_row, get_credits


def register_me(bot):

    @bot.message_handler(commands=["me"])
    def me_handler(message):
        user = message.from_user
        user_id = user.id

        # تأكيد وجود المستخدم في DB
        ensure_row(user_id)

        credits = get_credits(user_id)

        name = user.first_name or "NoName"
        username = f"@{user.username}" if user.username else "NoUsername"
        credits_text = "Unlimited" if credits == -1 else credits

        text = f"""
𝐀𝐜𝐜𝐨𝐮𝐧𝐭 𝐈𝐧𝐟𝐨

Name      : {name}
Username  : {username}
User ID   : {user_id}
Credits   : {credits_text}
"""



        bot.send_message(message.chat.id, text)