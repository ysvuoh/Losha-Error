import random
from telebot import types

from storage.repositories.users import create_or_update_user
from storage.repositories.credits import get_credits
from storage.repositories.bans import is_banned
from config.settings import OWNER_NAME, TOOL_BY 

VIDEO_LINKS = [
    "https://t.me/L_O_S_H_A_1/26",
    "https://t.me/L_O_S_H_A_1/27",
    "https://t.me/L_O_S_H_A_1/28",
    "https://t.me/L_O_S_H_A_1/34",
    "https://t.me/L_O_S_H_A_1/35",
    "https://t.me/L_O_S_H_A_1/41",
    "https://t.me/L_O_S_H_A_1/67",
    "https://t.me/L_O_S_H_A_1/148",
    "https://t.me/L_O_S_H_A_1/398",
]

def register_start(bot):

    @bot.message_handler(commands=["start"])
    def start_handler(message):
        user_id = message.from_user.id
        name = message.from_user.first_name or "User"
        username = message.from_user.username

        # 🚫 Ban check
        if is_banned(user_id):
            bot.send_message(
                message.chat.id,
                "🚫 You are banned from using this bot."
            )
            return

        # 👤 Create / Update user
        create_or_update_user(
            user_id=user_id,
            first_name=name,
            username=username
        )

        # 💳 Credits check
        balance = get_credits(user_id)

        # 🎥 Keyboard
        kb = types.InlineKeyboardMarkup()
        kb.add(
            types.InlineKeyboardButton(
                f"ϟ Tool By ⇾ {OWNER_NAME} ϟ",
                url="https://t.me/I_EOR"
            )
        )

        # 📝 Caption setup
        if balance == -1:
            caption = f"""✨ Welcome {name} ✨

💳 Credits : Unlimited

- Send your combo to check
ϟ Tool By ⇾ {TOOL_BY} ϟ
"""
        elif balance > 0:
            caption = f"""✨ Welcome {name} ✨

💳 Credits : {balance}

- Send your combo to check
- Use /buy to get more credits
ϟ Tool By ⇾ {TOOL_BY} ϟ
"""
        else:
            caption = f"""✨ Welcome {name} ✨

❌ No Credits Available

Use /buy to get credits
ϟ Tool By ⇾ {TOOL_BY} ϟ
"""

        # 🎬 Send video with new caption
        bot.send_video(
            chat_id=message.chat.id,
            video=random.choice(VIDEO_LINKS),
            caption=caption,
            reply_markup=kb
        )
