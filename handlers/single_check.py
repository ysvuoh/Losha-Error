import time
from utils.classify import classify_result
from utils.messages import (
    approved_message,
    charged_message,
    insufficient_funds_message,
    declined_message,
    hit_detected_message,
    get_user_name,
    dato
)
from config.settings import HIT_CHAT

def send_result(bot, chat_id, message_id, msg, pin=False):
    bot.edit_message_text(msg, chat_id=chat_id, message_id=message_id, parse_mode="HTML")
    if pin:
        bot.pin_chat_message(chat_id, message_id, disable_notification=True)

def run_single_check(bot, message, cc, gate_name, gate_func):
    ko = bot.reply_to(
        message,
        "<b>⏳ Please wait checking your card...</b>",
        parse_mode="HTML"
    ).message_id

    start_time = time.time()
    try:
        result = str(gate_func(cc))
    except Exception as e:
        result = f"Gateway Error: {e}"

    execution_time = round(time.time() - start_time, 2)
    
    # استخدام دالة التصنيف الموحدة لإصلاح مشكلة "order_not_approved"
    status = classify_result(result)
    user_name = get_user_name(message.from_user)
    
    msg = None
    hit_type = None
    pin = False

    if status == "APPROVED":
        msg = approved_message(cc, result, gate_name, execution_time, dato, checked_by_text=user_name)
        hit_type = "approved"
        pin = True
    elif status == "CHARGED":
        msg = charged_message(cc, result, gate_name, execution_time, dato, checked_by_text=user_name)
        hit_type = "charged"
        pin = True
    elif status == "FUNDS":
        msg = insufficient_funds_message(cc, result, gate_name, execution_time, dato, checked_by_text=user_name)
        hit_type = "funds"
        pin = True
    else:
        msg = declined_message(cc, result, gate_name, execution_time, dato, checked_by_text=user_name)
        hit_type = "declined"
        pin = False

    if msg:
        send_result(bot, message.chat.id, ko, msg, pin=pin)
        
    # إرسال HIT_CHAT للـ Charged و Funds و Approved
    if hit_type in ["charged", "funds", "approved"]:
        try:
            bot.send_message(
                HIT_CHAT,
                hit_detected_message(user_name, hit_type, execution_time, gate_name, checked_by_text=user_name),
                parse_mode="HTML"
            )
        except:
            pass