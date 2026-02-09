from storage.db import get_connection


def ensure_row(user_id: int):
    """
    Ensure user exists in credits table.
    """
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT OR IGNORE INTO credits (user_id, balance) VALUES (?, 0)",
        (user_id,)
    )
    conn.commit()
    conn.close()


def get_credits(user_id: int) -> int:
    """
    Returns current credits.
    -1 means unlimited.
    """
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT balance FROM credits WHERE user_id = ?",
        (user_id,)
    )
    row = cur.fetchone()
    conn.close()
    return row[0] if row else 0


def deduct_one_atomic(user_id: int) -> bool:
    """
    Deduct ONE credit atomically.
    Used for simple single checks.
    """
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        UPDATE credits
        SET balance = balance - 1
        WHERE user_id = ?
          AND balance > 0
          AND balance != -1
    """, (user_id,))
    success = cur.rowcount == 1
    conn.commit()
    conn.close()
    return success


def deduct_credits_atomic(user_id: int, amount: int) -> bool:
    """
    Atomically deduct a specific amount of credits.
    
    Rules:
    - balance must be >= amount
    - balance != -1 (unlimited)
    - prevents negative balance
    """
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        UPDATE credits
        SET balance = balance - ?
        WHERE user_id = ?
          AND balance != -1
          AND balance >= ?
    """, (amount, user_id, amount))
    success = cur.rowcount == 1
    conn.commit()
    conn.close()
    return success
