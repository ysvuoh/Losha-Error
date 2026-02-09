# File: utils/classify.py

def classify_result(text: str):
    """
    Classifies the result of a gate check based on its text content.
    Gives priority to 'charged' and 'funds' over 'approved'.
    """
    if not isinstance(text, str):
        return "DECLINED" # Handle non-string inputs

    t = text.lower()

    # 1. Priority: Charged
    if "charged" in t or "thank you for your donation" in t or "thank you" in t or "succeeded" in t:
        return "CHARGED"

    # 2. Priority: Insufficient Funds
    if "insufficient_funds" in t or "insufficient funds" in t or "fund" in t:
        return "FUNDS"

    # 3. Check for Approved (only if not charged or funds)
    if "approved" in t or "1000: approved" in t:
        return "APPROVED"

    # 4. Default: Declined
    return "DECLINED"
