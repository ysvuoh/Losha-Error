import random
from telebot import types

CHANNEL = "@L_O_S_H_A_1"
GROUP   = "@L_O_S_H_A_2"

VIDEO_LINKS = [
    "https://t.me/L_O_S_H_A_1/26",
    "https://t.me/L_O_S_H_A_1/27",
    "https://t.me/L_O_S_H_A_1/28",
    "https://t.me/L_O_S_H_A_1/31",
    "https://t.me/L_O_S_H_A_1/34",
    "https://t.me/L_O_S_H_A_1/35",
    "https://t.me/L_O_S_H_A_1/41",
    "https://t.me/L_O_S_H_A_1/67",
    "https://t.me/L_O_S_H_A_1/148",
]

def is_channel_subscribed(bot, user_id: int) -> bool:
    try:
        ch = bot.get_chat_member(CHANNEL, user_id)
        gr = bot.get_chat_member(GROUP, user_id)
        return ch.status in ("member", "administrator", "creator") and \
               gr.status in ("member", "administrator", "creator")
    except:
        return False

def send_channel_prompt(bot, chat_id, name=None):
    username = name or "there"

    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(types.InlineKeyboardButton("⚡ Bot Developer ⚡", url="https://t.me/I_EOR"))
    kb.row(
        types.InlineKeyboardButton("📢 Bot Channel", url="https://t.me/L_O_S_H_A_1"),
        types.InlineKeyboardButton("💬 Support Group", url="https://t.me/L_O_S_H_A_2"),
    )

    bot.send_video(
        chat_id=chat_id,
        video=random.choice(VIDEO_LINKS),
        caption=f"""✨ Hello {username} ✨

📌 You must join both the Bot Channel and the Support Group to use this bot.

✅ After subscribing, try the command again.
""",
        reply_markup=kb
    )