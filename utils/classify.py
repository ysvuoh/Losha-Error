def classify_result(text: str):
    """
    Classifies the result of a gate check based on its text content.
    Gives priority to 'charged' and 'funds' over 'approved'.
    """
    if not isinstance(text, str):
        return "DECLINED"

    t = text.lower()

    # 1. Priority: Charged
    if any(keyword in t for keyword in ["charged", "thank you", "succeeded", "payment successful", "donation successful"]):
        return "CHARGED"

    # 2. Priority: Insufficient Funds
    if any(keyword in t for keyword in ["insufficient_funds", "insufficient funds", "fund", "insufficient"]):
        return "FUNDS"

    # 3. Check for Approved (only if not charged or funds)
    if any(keyword in t for keyword in ["approved", "1000: approved", "approved (cvv)", "status: approved"]):
        return "APPROVED"

    # 4. Default: Declined
    return "DECLINED"
