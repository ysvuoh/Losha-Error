import random
import string
from storage.db import get_connection

def generate_code():
    """Generates a unique code like LOSHA-2026-XXXX"""
    chars = string.ascii_uppercase + string.digits
    return "LOSHA-2026-" + ''.join(random.choices(chars, k=6))

def create_code(credits: int = 0, max_uses: int = 1, vip_minutes: int = 0) -> str:
    """
    Creates a code in the database.

    :param credits: Amount of credits the code gives
    :param max_uses: How many times the code can be used
    :param vip_minutes: How many minutes of VIP the code grants
    :return: The generated code string
    """
    conn = get_connection()
    cur = conn.cursor()

    # Ensure uniqueness
    while True:
        code = generate_code()
        cur.execute("SELECT 1 FROM codes WHERE code = ?", (code,))
        if not cur.fetchone():
            break

    # Insert code into database
    cur.execute(
        """
        INSERT INTO codes (code, credits, max_uses, used_count, vip_minutes)
        VALUES (?, ?, ?, 0, ?)
        """,
        (code, credits, max_uses, vip_minutes)
    )

    conn.commit()
    conn.close()
    return code

def get_code_info(code: str):
    """Retrieve code info from database"""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT credits, max_uses, used_count, vip_minutes FROM codes WHERE code = ?",
        (code,)
    )
    row = cur.fetchone()
    conn.close()
    return row

def is_code_expired(code_info):
    """
    Dummy function for compatibility.
    We removed expiry_date, so codes never expire automatically.
    """
    return False  # Always False since we don't track expiry anymore
