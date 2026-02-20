def classify_result(text: str):
    if not isinstance(text, str):
        return "DECLINED"

    # تنظيف النص: تحويل لصغير، إزالة المسافات الزائدة
    t = text.lower().strip()

    # 1️⃣ المطابقة الدقيقة للرفض (Hard Declines)
    hard_declines_exact = [
        "declined",
        "card declined",
        "do not honor",
        "transaction declined",
        "payment declined",
        "status: declined",
        "approval failed",
        "order_not_approved" # حالة باي بال أصبحت رفضاً هنا
    ]
    if t in hard_declines_exact:
        return "DECLINED"

    # 2️⃣ رصيد غير كافٍ (Insufficient Funds)
    funds_exact = [
        "insufficient funds",
        "insufficient_funds",
        "not enough funds",
        "balance too low"
    ]
    if t in funds_exact:
        return "FUNDS"

    # 3️⃣ عمليات ناجحة مع سحب (Charged)
    charged_exact = [
        "charged",
        "charge succeeded",
        "payment successful",
        "donation successful",
        "payment completed",
        "transaction completed"
    ]
    if t in charged_exact:
        return "CHARGED"

    # 4️⃣ عمليات مقبولة بدون سحب (Approved / Auth)
    approved_exact = [
        "approved",
        "auth approved",
        "authorization approved",
        "authorization successful",
        "auth_success",
        "status: approved",
        "1000: approved"
    ]
    if t in approved_exact:
        return "APPROVED"

    # 5️⃣ حالات المخاطرة أو المراجعة (Risk / Review)
    risk_exact = [
        "risk",
        "review"
    ]
    if t in risk_exact:
        return "RISK"

    # 6️⃣ منطق البحث الجزئي الذكي (Fallback)
    # إذا لم يطابق النص بالكامل، نبحث عن كلمات مفتاحية مع استثناءات
    if "insufficient funds" in t:
        return "FUNDS"
    if "approved" in t and "not approved" not in t: 
        return "APPROVED"
    if "charged" in t or "success" in t:
        return "CHARGED"
    if "declined" in t or "fail" in t or "not approved" in t:
        return "DECLINED"

    # 7️⃣ الحالة الافتراضية
    return "UNKNOWN"
