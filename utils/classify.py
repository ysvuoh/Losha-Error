def classify_result(text: str):
    if not isinstance(text, str):
        return "DECLINED"

    t = text.lower()

    # 0. Explicit negative approvals (HIGHEST priority)
    negative_approved = [
        "not approved",
        "order not approved",
        "approved=false",
        "approval failed",
        "approval declined",
        "status: declined",
        "declined",
        "do not honor"
    ]

    if any(x in t for x in negative_approved):
        return "DECLINED"

    # 1. Charged
    if any(x in t for x in [
        "charged",
        "payment successful",
        "donation successful",
        "thank you",
        "succeeded"
    ]):
        return "CHARGED"

    # 2. Insufficient Funds
    if any(x in t for x in [
        "insufficient_funds",
        "insufficient funds",
        "not enough funds",
        "balance too low"
    ]):
        return "FUNDS"

    # 3. Approved (ONLY clean approvals)
    approved_keywords = [
        "approved (cvv)",
        "auth approved",
        "status: approved",
        "1000: approved"
    ]

    if any(x in t for x in approved_keywords):
        return "APPROVED"

    return "DECLINED"
