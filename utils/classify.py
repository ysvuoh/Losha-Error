def classify_result(text: str):
    if not isinstance(text, str):
        return "DECLINED"

    t = text.lower()

    # 1️⃣ Hard Declines (HIGHEST priority)
    hard_declines = [
        "do not honor",
        "card declined",
        "declined",
        "not approved",
        "approval failed",
        "approval declined",
        "status: declined",
        "transaction declined",
        "payment declined"
    ]

    if any(x in t for x in hard_declines):
        return "DECLINED"

    # 2️⃣ Insufficient Funds
    funds = [
        "insufficient_funds",
        "insufficient funds",
        "not enough funds",
        "balance too low"
    ]

    if any(x in t for x in funds):
        return "FUNDS"

    # 3️⃣ Charged (ONLY real charge indicators)
    charged = [
        "charged",
        "charge succeeded",
        "payment successful",
        "donation successful",
        "payment completed",
        "transaction completed"
    ]

    if any(x in t for x in charged):
        return "CHARGED"

    # 4️⃣ Approved / Auth
    approved = [
        "approved",
        "auth approved",
        "authorization approved",
        "authorization successful",
        "auth_success",
        "status: approved",
        "1000: approved"
    ]

    if any(x in t for x in approved):
        return "APPROVED"

    # 5️⃣ Risk / Review
    risk = [
        "risk",
        "review",
        "verification required",
        "3d secure",
        "authentication required"
    ]

    if any(x in t for x in risk):
        return "RISK"

    # 6️⃣ Default
    return "DECLINED"
