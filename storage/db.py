import sqlite3
from pathlib import Path

# ===== DATABASE PATH =====
DB_PATH = Path(__file__).parent / "db.sqlite"


# ==========================================================
# CONNECTION
# ==========================================================
def get_connection():
    """
    Return a SQLite connection with production-grade stability.
    Uses the default journal mode (DELETE), no WAL.
    """

    # Ensure folder exists
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB_PATH, isolation_level=None)

    # ===== PERFORMANCE + STABILITY =====
    conn.execute("PRAGMA journal_mode=DELETE;")  # Default journal mode
    conn.execute("PRAGMA synchronous=FULL;")     # Maximum safety


    return conn


# ==========================================================
# DATABASE INITIALIZATION
# ==========================================================
def init_db():
    """
    Initialize database and create tables if they don't exist.
    Safe to run on every startup.
    """

    with get_connection() as conn:
        cur = conn.cursor()

        # ================= USERS =================
        cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT
        )
        """)

        # ================= CREDITS =================
        cur.execute("""
        CREATE TABLE IF NOT EXISTS credits (
            user_id INTEGER PRIMARY KEY,
            balance INTEGER NOT NULL DEFAULT 0
        )
        """)

        # ================= SESSIONS =================
        cur.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            user_id INTEGER PRIMARY KEY,
            active INTEGER NOT NULL DEFAULT 0,
            gate_key TEXT,
            current_index INTEGER DEFAULT 0,
            total_cards INTEGER DEFAULT 0,
            cards_data TEXT,
            approved INTEGER DEFAULT 0,
            charged INTEGER DEFAULT 0,
            funds INTEGER DEFAULT 0,
            declined INTEGER DEFAULT 0,
            chat_id INTEGER,
            message_id INTEGER
        )
        """)

        # ================= BANS =================
        cur.execute("""
        CREATE TABLE IF NOT EXISTS bans (
            user_id INTEGER PRIMARY KEY,
            reason TEXT,
            banned_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """)

        # ================= BIN BANS =================
        cur.execute("""
        CREATE TABLE IF NOT EXISTS bin_bans (
            bin TEXT PRIMARY KEY,
            banned_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """)

        # ================= GATE STATE =================
        cur.execute("""
        CREATE TABLE IF NOT EXISTS gate_state (
            gate_key TEXT PRIMARY KEY,
            enabled INTEGER NOT NULL DEFAULT 1,
            max_cards INTEGER NOT NULL DEFAULT 200,
            cost_per_card INTEGER NOT NULL DEFAULT 1
        )
        """)

        # ================= CODES =================
        cur.execute("""
        CREATE TABLE IF NOT EXISTS codes (
            code TEXT PRIMARY KEY,
            credits INTEGER NOT NULL,
            max_uses INTEGER NOT NULL,
            used_count INTEGER NOT NULL DEFAULT 0,
            vip_minutes INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """)

        # تأكد من وجود vip_minutes لو القاعدة قديمة
        cur.execute("PRAGMA table_info(codes)")
        columns = [col[1] for col in cur.fetchall()]
        if "vip_minutes" not in columns:
            cur.execute("ALTER TABLE codes ADD COLUMN vip_minutes INTEGER DEFAULT 0")

        # ================= CODE REDEEMS =================
        cur.execute("""
        CREATE TABLE IF NOT EXISTS code_redeems (
            code TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            redeemed_at TEXT DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (code, user_id)
        )
        """)

        # ================= BUY PACKAGES =================
        cur.execute("""
        CREATE TABLE IF NOT EXISTS buy_packages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            credits INTEGER NOT NULL,
            stars INTEGER NOT NULL,
            bonus INTEGER NOT NULL DEFAULT 0,
            active INTEGER NOT NULL DEFAULT 1
        )
        """)

        # ================= BUY ORDERS =================
        cur.execute("""
        CREATE TABLE IF NOT EXISTS buy_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            credits INTEGER NOT NULL,
            stars INTEGER NOT NULL,
            bonus INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """)

        # ================= HIT COUNTER =================
        cur.execute("""
        CREATE TABLE IF NOT EXISTS hit_counter (
            id INTEGER PRIMARY KEY CHECK(id = 1),
            last_hit INTEGER NOT NULL DEFAULT 0
        )
        """)
        cur.execute("""
        INSERT OR IGNORE INTO hit_counter (id, last_hit)
        VALUES (1, 0)
        """)


# ==========================================================
# HIT COUNTER
# ==========================================================
def get_next_hit_number():
    """
    Retrieve last hit, increment by 1, update table,
    and return new hit number safely.
    """
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT last_hit FROM hit_counter WHERE id = 1")
        row = cur.fetchone()

        last_hit = row[0] if row else 0
        next_hit = last_hit + 1

        cur.execute(
            "UPDATE hit_counter SET last_hit = ? WHERE id = 1",
            (next_hit,)
        )

    return next_hit
