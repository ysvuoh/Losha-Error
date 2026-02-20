# bin_checker.py

import threading
import requests
from storage.repositories.bans import is_banned
from storage.db import get_connection

from security.channel_guard import is_channel_subscribed, send_channel_prompt

def register_bin_checker(bot):
    """
    يسجل معالج الأوامر للبحث عن معلومات BIN.
    الأوامر المدعومة: .bin <رقم> أو /bin <رقم>
    """
    @bot.message_handler(
        func=lambda message: message.text and 
        (message.text.lower().startswith('.bin') or message.text.lower().startswith('/bin'))
    )
    

    
    def handle_bin_command(message):
        # تشغيل المهمة في خيط منفصل لتجنب حظر البوت أثناء طلب الـ API
        threading.Thread(target=bin_lookup_worker, args=(bot, message)).start()

def get_bin_info(bin_number):
    """
    يجلب معلومات الـ BIN من API خارجي.
    """
    try:
        # التأكد من أننا نستخدم أول 6 أرقام فقط
        bin_to_check = bin_number[:6]
        
        # استدعاء الـ API
        response = requests.get(f"https://bins.antipublic.cc/bins/{bin_to_check}", timeout=10)
        response.raise_for_status()  # يطلق استثناء إذا كان هناك خطأ في الطلب (مثل 404, 500)
        
        api_data = response.json()
        
        # استخراج البيانات مع قيم افتراضية في حال عدم وجودها
        brand = api_data.get("brand", "N/A")
        card_type = api_data.get("type", "N/A")
        level = api_data.get("level", "N/A")
        bank = api_data.get("bank", "N/A")
        country_name = api_data.get("country_name", "N/A")
        country_flag = api_data.get("country_flag", "") # علم الدولة قد يكون فارغًا
        
        # تنسيق النص للرسالة
        info_text = f"""<b>Brand ➜</b> {brand} - {card_type} - {level}
<b>Bank ➜</b> {bank}
<b>Country ➜</b> {country_name} {country_flag}
"""
        return info_text

    except requests.exceptions.RequestException as e:
        print(f"BIN API Request Error: {e}")
        return "❌ Service unavailable or invalid BIN."
    except Exception as e:
        print(f"BIN Info Error: {e}")
        return "❌ No information found for this BIN."

def bin_lookup_worker(bot, message):
    """
    المهمة التي تعمل في الخلفية لمعالجة طلب الـ BIN.
    """
    try:
        # استخراج رقم الـ BIN من الرسالة
        command_parts = message.text.split()
        if len(command_parts) < 2:
            bot.reply_to(message, "<b>Please provide a BIN after the command.\nExample: <code>/bin 457173</code></b>", parse_mode="HTML")
            return
            
        bin_number = command_parts[1]

        # إرسال رسالة مؤقتة
        temp_message = bot.reply_to(message, "<b>Searching for BIN info... ⏳</b>", parse_mode="HTML")

        # جلب معلومات الـ BIN
        info_result = get_bin_info(bin_number)
        
        # تنسيق الرسالة النهائية
        final_text = f"""
<b>💳 BIN Lookup Result</b>

<b>BIN ➜</b> <code>{bin_number[:6]}</code>
{info_result}
"""
        # تعديل الرسالة المؤقتة بالنتيجة النهائية
        bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=temp_message.message_id,
            text=final_text,
            parse_mode="HTML"
        )

    except Exception as e:
        print(f"BIN Worker Error: {e}")
        bot.reply_to(message, "An unexpected error occurred while processing your request.")
