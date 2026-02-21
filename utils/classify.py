def classify_result(text: str):
    if not isinstance(text, str):
        return "DECLINED"

    # تنظيف النص
    t = text.lower().strip()

    # 1️⃣ المطابقة الدقيقة للرفض (Hard Declines)
    hard_declines_exact = [
        "declined", "card declined", "do not honor", "transaction declined",
        "payment declined", "status: declined", "approval failed", "order_not_approved"
    ]
    if t in hard_declines_exact:
        return "DECLINED"

    # 2️⃣ رصيد غير كافٍ
    funds_exact = ["insufficient funds", "insufficient_funds", "not enough funds", "balance too low"]
    if t in funds_exact:
        return "FUNDS"

    # 3️⃣ عمليات ناجحة مع سحب
    charged_exact = [
        "charged", "charge succeeded", "payment successful", "donation successful",
        "payment completed", "transaction completed"
    ]
    if t in charged_exact:
        return "CHARGED"

    # 4️⃣ عمليات مقبولة بدون سحب
    approved_exact = [
        "approved", "auth approved", "authorization approved", "authorization successful",
        "auth_success", "status: approved", "1000: approved"
    ]
    if t in approved_exact:
        return "APPROVED"

    # 5️⃣ حالات المخاطرة أو المراجعة
    risk_exact = ["risk", "review"]
    if t in risk_exact:
        return "RISK"

    # 6️⃣ منطق البحث الجزئي الذكي (Fallback) - تم إعادة ترتيب الشروط هنا
    
    # ✅ أولاً: تحقق من حالات الرفض الصريحة
    if "declined" in t or "fail" in t or "not approved" in t:
        return "DECLINED"
        
    # ثانياً: تحقق من الرصيد
    if "insufficient funds" in t:
        return "FUNDS"
        
    # ثالثاً: تحقق من القبول (فقط إذا لم تكن مرفوضة)
    if "approved" in t: 
        return "APPROVED"
        
    # رابعاً: تحقق من العمليات الناجحة
    if "charged" in t or "success" in t:
        return "CHARGED"

    # 7️⃣ الحالة الافتراضية
    return "UNKNOWN"

