def classify_result(text: str):
    if not isinstance(text, str):
        return "DECLINED"

    # تنظيف النص: تحويل لصغير، إزالة المسافات الزائدة
    t = text.lower().strip()

    # 1️⃣ التحقق الفوري من حالات الرفض الصريحة (لمنع تداخلها مع كلمة approved)
    # أي نص يحتوي على "not approved" أو "order_not_approved" أو "declined" أو "fail" يُصنف كرفض فوراً
    if "not approved" in t or "order_not_approved" in t or "declined" in t or "fail" in t:
        return "DECLINED"

    # 2️⃣ المطابقة الدقيقة للرفض (Hard Declines)
    hard_declines_exact = [
        "card declined",
        "do not honor",
        "transaction declined",
        "payment declined",
        "status: declined",
        "approval failed"
    ]
    if t in hard_declines_exact:
        return "DECLINED"

    # 3️⃣ رصيد غير كافٍ (Insufficient Funds)
    funds_exact = [
        "insufficient funds",
        "insufficient_funds",
        "not enough funds",
        "balance too low"
    ]
    if "insufficient funds" in t or t in funds_exact:
        return "FUNDS"

    # 4️⃣ عمليات ناجحة مع سحب (Charged)
    charged_exact = [
        "charged",
        "charge succeeded",
        "payment successful",
        "donation successful",
        "payment completed",
        "transaction completed"
    ]
    if "charged" in t or "success" in t or t in charged_exact:
        return "CHARGED"

    # 5️⃣ عمليات مقبولة بدون سحب (Approved / Auth)
    approved_exact = [
        "approved",
        "auth approved",
        "authorization approved",
        "authorization successful",
        "auth_success",
        "status: approved",
        "1000: approved"
    ]
    if "approved" in t or t in approved_exact:
        return "APPROVED"

    # 6️⃣ حالات المخاطرة أو المراجعة (Risk / Review)
    risk_exact = ["risk", "review"]
    if t in risk_exact:
        return "RISK"

    # 7️⃣ الحالة الافتراضية
    return "UNKNOWN"
