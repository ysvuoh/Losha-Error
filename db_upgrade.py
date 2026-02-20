import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "db.sqlite"

def upgrade_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # إنشاء جدول vip_status لو مش موجود
    cur.execute("""
    CREATE TABLE IF NOT EXISTS vip_status (
        user_id INTEGER PRIMARY KEY,
        expires_at TEXT NOT NULL,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )
    """)

    conn.commit()
    conn.close()
    print("✅ vip_status table created successfully")

if __name__ == "__main__":
    upgrade_db()
