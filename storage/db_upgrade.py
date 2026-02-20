import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "db.sqlite"

def get_connection():
    conn = sqlite3.connect(DB_PATH, isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL;")  # better crash safety
    conn.execute("PRAGMA synchronous=NORMAL;")  # immediate writes
    return conn

def ensure_columns(table, columns):
    """
    Make sure all columns exist in the table.
    - table: table name
    - columns: dict { 'column_name': 'SQL_TYPE DEFAULT ...' }
    """
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(f"PRAGMA table_info({table})")
        existing = [row[1] for row in cur.fetchall()]
        for col, definition in columns.items():
            if col not in existing:
                print(f"➕ Adding column {col} to table {table}")
                cur.execute(f"ALTER TABLE {table} ADD COLUMN {col} {definition}")

def upgrade_db():
    # ===== USERS =====
    ensure_columns('users', {
        'username': 'TEXT',
        'first_name': 'TEXT',
        'vip_level': 'INTEGER DEFAULT 0'
    })

    # ===== SESSIONS =====
    ensure_columns('sessions', {
        'active': 'INTEGER DEFAULT 0',
        'gate_key': 'TEXT',
        'current_index': 'INTEGER DEFAULT 0',
        'total_cards': 'INTEGER DEFAULT 0',
        'cards_data': 'TEXT',
        'approved': 'INTEGER DEFAULT 0',
        'charged': 'INTEGER DEFAULT 0',
        'funds': 'INTEGER DEFAULT 0',
        'declined': 'INTEGER DEFAULT 0',
        'chat_id': 'INTEGER',
        'message_id': 'INTEGER'
    })

    # ===== HIT COUNTER =====
    ensure_columns('hit_counter', {
        'last_hit': 'INTEGER DEFAULT 0'
    })
    # make sure there is one row
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("INSERT OR IGNORE INTO hit_counter (id, last_hit) VALUES (1,0)")

if __name__ == "__main__":
    upgrade_db()
    print("✅ Database upgrade completed successfully")
