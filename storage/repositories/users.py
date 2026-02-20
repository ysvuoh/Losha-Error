from storage.db import get_connection

def get_user(user_id):
    """Fetch a user by ID"""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()
    return row

def create_or_update_user(user_id, username, first_name):
    """Insert new user or update existing user's username and first_name"""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO users (id, username, first_name)
        VALUES (?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            username=excluded.username,
            first_name=excluded.first_name
    """, (user_id, username, first_name))
    conn.commit()
    conn.close()