import threading
import requests
import random
import re
from faker import Faker
from telebot import types
from storage.repositories.bans import is_banned
from storage.db import get_connection

from security.channel_guard import is_channel_subscribed, send_channel_prompt

def register_gen(bot):
    @bot.message_handler(
        func=lambda message: message.text and 
        (message.text.lower().startswith('.gen') or message.text.lower().startswith('/gen'))
    )
    

    
    def respond_to_gen(message):
        # إرسال رسالة أولية لإعلام المستخدم بالبدء
        ko = bot.reply_to(message, "<b>Generating cards...⌛</b>", parse_mode="HTML").message_id
        
        # تشغيل المهمة في خيط منفصل لتجنب حظر البوت
        threading.Thread(target=worker_gen, args=(bot, message, ko)).start()

# --- الدوال المساعدة لتوليد البطاقات ---
def generate_check_digit(num):
    # (Luhn algorithm)
    num_list = [int(x) for x in num]
    for i in range(len(num_list) - 1, -1, -2):
        num_list[i] *= 2
        if num_list[i] > 9:
            num_list[i] -= 9
    return (10 - sum(num_list) % 10) % 10

def generate_credit_card_info(card_number, expiry_month, expiry_year, cvv):
    # تحديد طول الرقم بناءً على النوع (AMEX يبدأ بـ 3)
    target_length = 15 if card_number.startswith("3") else 16
    
    generated_num = str(card_number)
    
    # إكمال الأرقام الناقصة بشكل عشوائي
    while len(generated_num) < (target_length - 1):
        generated_num += str(random.randint(0, 9))
        
    # حساب رقم التحقق الأخير
    check_digit = generate_check_digit(generated_num)
    credit_card_number = generated_num + str(check_digit)
    
    return f"{credit_card_number}|{str(expiry_month).zfill(2)}|{str(expiry_year)[-2:]}|{str(cvv).zfill(3)}"

# --- المهمة الفعلية لتوليد البطاقات ---
def worker_gen(bot, message, ko):
    try:
        # استخراج البيانات من الرسالة باستخدام التعبيرات النمطية
        match = re.search(r'(\d{6,16})\D*(\d{1,2}|xx)?\D*(\d{2,4}|xx)?\D*(\d{3,4}|xxx)?', message.text)
        
        if not match:
            bot.edit_message_text(
                chat_id=message.chat.id, 
                message_id=ko, 
                text='''<b>Invalid input. Please provide a BIN.
Example: <code>/gen 412236xxxx|xx|2023|xxx</code></b>''', 
                parse_mode="HTML"
            )
            return

        card_number_input = match.group(1)
        bin_num = card_number_input[:6]

        # التحقق من صحة BIN
        if len(bin_num) < 6 or bin_num[0] not in ['3', '4', '5', '6']:
            bot.edit_message_text(
                chat_id=message.chat.id, 
                message_id=ko, 
                text='<b>❌ BIN not recognized. Please enter a valid BIN.</b>', 
                parse_mode="HTML"
            )
            return

        response_message = ""
        # توليد 10 بطاقات
        for _ in range(10):
            month = int(match.group(2)) if match.group(2) and match.group(2) != 'xx' else random.randint(1, 12)
            year = int(match.group(3)) if match.group(3) and match.group(3) != 'xx' else random.randint(2025, 2029)
            
            # تحديد طول CVV بناءً على نوع البطاقة
            is_amex = card_number_input.startswith("3")
            cvv_length = 4 if is_amex else 3
            cvv_placeholder = 'xxxx' if is_amex else 'xxx'
            
            if match.group(4) and match.group(4) != cvv_placeholder:
                cvv = int(match.group(4))
            else:
                cvv = random.randint(10**(cvv_length-1), 10**cvv_length - 1)

            credit_card_info = generate_credit_card_info(card_number_input, month, year, cvv)
            response_message += f"<code>{credit_card_info}</code>\n"

        # جلب معلومات الـ BIN
        try:
            bin_data = requests.get(f'https://bins.antipublic.cc/bins/{bin_num}').json()
            brand = bin_data.get('brand', 'N/A')
            card_type = bin_data.get('type', 'N/A')
            level = bin_data.get('level', 'N/A')
            country = bin_data.get('country_name', 'N/A')
            country_flag = bin_data.get('country_flag', '')
            bank = bin_data.get('bank', 'N/A')
        except Exception:
            brand, card_type, level, country, country_flag, bank = ('N/A',) * 6

        # إرسال النتيجة النهائية للمستخدم
        final_text = f"""
<b>💳 Generated Cards</b>

<b>BIN ➜</b> <code>{bin_num}</code>

{response_message}
<b>BIN Info ➜</b> {brand} - {card_type} - {level}
<b>Bank ➜</b> {bank}
<b>Country ➜</b> {country} {country_flag}
"""
        bot.edit_message_text(chat_id=message.chat.id, message_id=ko, text=final_text, parse_mode="HTML")

    except Exception as e:
        bot.edit_message_text(
            chat_id=message.chat.id, 
            message_id=ko, 
            text=f"❌ An unexpected error occurred: {e}"
        )
        print(f"GEN ERROR: {e}")



