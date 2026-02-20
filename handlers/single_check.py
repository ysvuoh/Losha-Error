import time

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
    r = result.lower()

    if "approved" in r:
        msg = approved_message(cc, result, gate_name, execution_time, dato)
        send_result(bot, message.chat.id, ko, msg, pin=True)
        return

    if "charged" in r or "thank you for your donation" in r:
        msg = charged_message(cc, result, gate_name, execution_time, dato)
        send_result(bot, message.chat.id, ko, msg, pin=True)
        return

    if "fund" in r or "insufficient" in r:
        msg = insufficient_funds_message(cc, result, gate_name, execution_time, dato)
        send_result(bot, message.chat.id, ko, msg, pin=True)
        return

    # Declined
    msg = declined_message(cc, result, gate_name, execution_time, dato)
    send_result(bot, message.chat.id, ko, msg, pin=False)