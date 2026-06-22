import sqlite3
import os

# 可用 DB_PATH 環境變數覆寫，部署時指向持久磁碟（如 Render 的 /var/data/ocds.db）
DB_PATH = os.environ.get("DB_PATH", os.path.join(os.path.dirname(__file__), "ocds.db"))


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    db_dir = os.path.dirname(DB_PATH)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS decisions (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'active'
        );

        CREATE TABLE IF NOT EXISTS options (
            id TEXT PRIMARY KEY,
            decision_id TEXT REFERENCES decisions(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            description TEXT DEFAULT '',
            benefit REAL DEFAULT 5,
            cost REAL DEFAULT 5,
            risk REAL DEFAULT 5,
            net_value REAL,
            is_chosen INTEGER DEFAULT 0,
            is_important INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            option_id TEXT REFERENCES options(id) ON DELETE CASCADE,
            tag TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS user_preferences (
            key TEXT PRIMARY KEY,
            value TEXT
        );
    """)
    conn.commit()
    conn.close()
