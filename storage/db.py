import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "db.sqlite"

def get_connection():
    """Return a SQLite connection"""
    return sqlite3.connect(DB_PATH, isolation_level=None)


def init_db():
    """Initialize database and create tables if not exist"""
    with get_connection() as conn:
        cur = conn.cursor()

        # ===== USERS =====
        cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT
        )
        """)

        # ===== CREDITS =====
        cur.execute("""
        CREATE TABLE IF NOT EXISTS credits (
            user_id INTEGER PRIMARY KEY,
            balance INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
        """)

        # ===== SESSIONS =====
        cur.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            user_id INTEGER PRIMARY KEY,
            active INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
        """)

        # ===== BANS =====
        cur.execute("""
        CREATE TABLE IF NOT EXISTS bans (
            user_id INTEGER PRIMARY KEY,
            reason TEXT,
            banned_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
        """)

        # ===== GATE STATE =====
        cur.execute("""
        CREATE TABLE IF NOT EXISTS gate_state (
            gate_key TEXT PRIMARY KEY,
            enabled INTEGER NOT NULL DEFAULT 1,
            max_cards INTEGER NOT NULL DEFAULT 200,
            cost_per_card INTEGER NOT NULL DEFAULT 1
        )
        """)

        # ===== CODES =====
        cur.execute("""
        CREATE TABLE IF NOT EXISTS codes (
            code TEXT PRIMARY KEY,
            credits INTEGER NOT NULL,
            max_uses INTEGER NOT NULL,
            used_count INTEGER NOT NULL DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS code_redeems (
            code TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            redeemed_at TEXT DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (code, user_id),
            FOREIGN KEY(code) REFERENCES codes(code),
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
        """)

        # ===== BUY PACKAGES =====
        cur.execute("""
        CREATE TABLE IF NOT EXISTS buy_packages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            credits INTEGER NOT NULL,
            stars INTEGER NOT NULL,
            bonus INTEGER NOT NULL DEFAULT 0,
            active INTEGER NOT NULL DEFAULT 1
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS buy_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            credits INTEGER NOT NULL,
            stars INTEGER NOT NULL,
            bonus INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
        """)

        # ===== HIT COUNTER =====
        cur.execute("""
        CREATE TABLE IF NOT EXISTS hit_counter (
            id INTEGER PRIMARY KEY CHECK(id = 1),
            last_hit INTEGER NOT NULL DEFAULT 0
        )
        """)

        # إدخال الصف الافتراضي للعداد
        cur.execute("INSERT OR IGNORE INTO hit_counter (id, last_hit) VALUES (1, 0)")


# ===== NEW FUNCTION =====
def get_next_hit_number():
    """Retrieve last hit, increment by 1, update table, and return new hit number"""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT last_hit FROM hit_counter WHERE id = 1")
        row = cur.fetchone()
        last_hit = row[0] if row else 0
        next_hit = last_hit + 1
        cur.execute("UPDATE hit_counter SET last_hit = ? WHERE id = 1", (next_hit,))
    return next_hit
