def classify_result(text: str):
    """
    Classifies the result of a gate check based on its text content.
    Gives priority to 'charged' and 'funds' over 'approved'.
    """
    t = text.lower()
    if "charged" in t or "thank you for your donation" in t or "thank you" in t:
        return "CHARGED"
    if "insufficient_funds" in t or "insufficient funds" in t or "fund" in t:
        return "FUNDS"
    # Check for approved only if not charged or funds
    if "approved" in t or "1000: approved" in t:
        return "APPROVED"
    return "DECLINED"
