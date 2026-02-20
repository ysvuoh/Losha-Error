from telebot import types
from storage.repositories import gates

# هذا القاموس يربط مفتاح البوابة باسمها الكامل الذي سيعرض للمستخدم
GATE_NAMES = {
    "stripe_auth": "Stripe Auth",
    "shopify_charge": "Shopify Charge",
    "braintree_auth": "Braintree Auth",
    "stripe_charge": "Stripe Charge",
    "paypal_donation": "Paypal Donation",
}

def register_help_command(bot):
    @bot.message_handler(commands=['help'])
    def help_handler(message):
        # نبدأ ببناء الرسالة
        help_text = "<b>🤖 قائمة أوامر البوت وأسعار الفحص 🤖</b>\n\n"
        help_text += "<b>═══ أوامر الفحص ═══</b>\n"
        help_text += "<code>/str [cc]</code> - فحص البطاقة عبر Stripe Auth\n"
        help_text += "<code>/sh [cc]</code> - فحص البطاقة عبر Shopify Charge\n"
        help_text += "<code>/br [cc]</code> - فحص البطاقة عبر Braintree Auth\n"
        help_text += "<code>/st [cc]</code> - فحص البطاقة عبر Stripe Charge\n"
        help_text += "<code>/pp [cc]</code> - فحص البطاقة عبر Paypal Donation\n\n"
        
        help_text += "<b>═══ أوامر أخرى ═══</b>\n"
        help_text += "<code>/credits</code> - لعرض رصيدك الحالي من النقاط\n"
        help_text += "<code>/buy</code> - لشراء نقاط أو باقات VIP\n"
        help_text += "<code>/redeem [code]</code> - لاستخدام كود واستلام النقاط\n\n"

        help_text += "<b>═══ أسعار الفحص (نقطة/بطاقة) ═══</b>\n"
        
        try:
            # نحاول جلب تكلفة كل بوابة من قاعدة البيانات
            for gate_key, gate_name in GATE_NAMES.items():
                cost = gates.get_cost(gate_key)
                # نضيف سطرًا لكل بوابة مع تكلفتها
                help_text += f"• {gate_name}: <b>{cost} نقطة</b>\n"
        except Exception as e:
            # في حال حدوث خطأ، نعرض رسالة تفيد بذلك
            print(f"Error fetching gate costs: {e}")
            help_text += "لم نتمكن من جلب الأسعار حاليًا، يرجى المحاولة لاحقًا.\n"

        help_text += "\n<i>الأسعار قد تتغير بواسطة الأدمن.</i>"

        # إرسال الرسالة النهائية للمستخدم
        bot.reply_to(message, help_text, parse_mode="HTML")

