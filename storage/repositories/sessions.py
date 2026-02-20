from storage.db import get_connection
import json

def has_active_session(user_id: int) -> bool:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT active FROM sessions WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()
    return bool(row and row[0] == 1)

def save_session(user_id, gate_key, current_index, total_cards, cards_data, approved, charged, funds, declined, chat_id, message_id, active=1):
    """حفظ حالة الجلسة بالكامل في قاعدة البيانات"""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT OR REPLACE INTO sessions 
        (user_id, active, gate_key, current_index, total_cards, cards_data, approved, charged, funds, declined, chat_id, message_id) 
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (user_id, active, gate_key, current_index, total_cards, json.dumps(cards_data), approved, charged, funds, declined, chat_id, message_id))
    conn.commit()
    conn.close()

def get_session(user_id):
    """استرجاع بيانات الجلسة للمستخدم"""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM sessions WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()
    if row:
        # تحويل الصف إلى قاموس لسهولة التعامل
        return {
            "user_id": row[0],
            "active": row[1],
            "gate_key": row[2],
            "current_index": row[3],
            "total_cards": row[4],
            "cards_data": json.loads(row[5]) if row[5] else [],
            "approved": row[6],
            "charged": row[7],
            "funds": row[8],
            "declined": row[9],
            "chat_id": row[10],
            "message_id": row[11]
        }
    return None

def get_all_active_sessions():
    """استرجاع كل الجلسات التي كانت تعمل قبل توقف البوت"""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM sessions WHERE active = 1")
    rows = cur.fetchall()
    conn.close()
    return [row[0] for row in rows]

def end_session(user_id: int):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE sessions SET active = 0 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def online_count() -> int:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM sessions WHERE active = 1")
    count = cur.fetchone()[0]
    conn.close()
    return count
