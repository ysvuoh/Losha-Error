from storage.db import get_connection

def ban_user(user_id: int, reason: str = ""):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT OR REPLACE INTO bans (user_id, reason) VALUES (?, ?)",
        (user_id, reason)
    )
    conn.commit()
    conn.close()

def unban_user(user_id: int):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM bans WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def is_banned(user_id: int) -> bool:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM bans WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()
    return row is not None

def list_bans():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT user_id, reason, banned_at FROM bans ORDER BY banned_at DESC"
    )
    rows = cur.fetchall()
    conn.close()
    return rows