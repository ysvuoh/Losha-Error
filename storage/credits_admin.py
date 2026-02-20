from storage.repositories.credits import get_credits, ensure_row
from storage.db import get_connection

def add_credits(user_id:int, amount:int):
    ensure_row(user_id)
    conn=get_connection(); cur=conn.cursor()
    cur.execute('UPDATE credits SET balance = balance + ? WHERE user_id = ?', (amount,user_id))
    conn.commit(); conn.close()

def set_unlimited(user_id:int):
    ensure_row(user_id)
    conn=get_connection(); cur=conn.cursor()
    cur.execute('UPDATE credits SET balance = -1 WHERE user_id = ?', (user_id,))
    conn.commit(); conn.close()
