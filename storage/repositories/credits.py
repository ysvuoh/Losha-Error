from storage.db import get_connection


def get_credits(user_id: int) -> int:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT balance FROM credits WHERE user_id = ?",
        (user_id,)
    )
    row = cur.fetchone()
    conn.close()
    return row[0] if row else 0


def ensure_row(user_id: int):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT OR IGNORE INTO credits (user_id, balance) VALUES (?, 0)",
        (user_id,)
    )
    conn.commit()
    conn.close()


def deduct_one_atomic(user_id: int) -> bool:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE credits SET balance = balance - 1 "
        "WHERE user_id = ? AND balance > 0",
        (user_id,)
    )
    success = cur.rowcount == 1
    conn.commit()
    conn.close()
    return success


def deduct_credits(user_id: int, amount: int) -> bool:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE credits "
        "SET balance = balance - ? "
        "WHERE user_id = ? "
        "AND balance != -1 "
        "AND balance >= ?",
        (amount, user_id, amount)
    )
    success = cur.rowcount == 1
    conn.commit()
    conn.close()
    return success
