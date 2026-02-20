from storage.db import get_connection

def ban_bin(bin_number):
    """حظر BIN معين"""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("INSERT OR IGNORE INTO bin_bans (bin) VALUES (?)", (str(bin_number),))

def unban_bin(bin_number):
    """إلغاء حظر BIN معين"""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM bin_bans WHERE bin = ?", (str(bin_number),))

def is_bin_banned(bin_number):
    """التحقق مما إذا كان الـ BIN محظوراً"""
    # نأخذ أول 6 أرقام من الـ BIN للتحقق
    bin_6 = str(bin_number)[:6]
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM bin_bans WHERE bin = ?", (bin_6,))
        return cur.fetchone() is not None

def list_banned_bins():
    """قائمة بكل الـ BINs المحظورة"""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT bin, banned_at FROM bin_bans ORDER BY banned_at DESC")
        return cur.fetchall()
