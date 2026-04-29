import sqlite3
from pathlib import Path


DB_PATH = Path(__file__).with_name("notified.sqlite3")


def connect(db_path: str | None = None):
    conn = sqlite3.connect(db_path or DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS notified_races (
            key TEXT PRIMARY KEY,
            race_id TEXT NOT NULL,
            mode TEXT NOT NULL,
            title TEXT NOT NULL,
            axis TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    return conn


def already_notified(conn, key: str) -> bool:
    cur = conn.execute("SELECT 1 FROM notified_races WHERE key = ?", (key,))
    return cur.fetchone() is not None


def save_notified(conn, *, key: str, race_id: str, mode: str, title: str, axis: str = "") -> None:
    conn.execute(
        "INSERT OR IGNORE INTO notified_races(key, race_id, mode, title, axis) VALUES (?, ?, ?, ?, ?)",
        (key, race_id, mode, title, axis),
    )
    conn.commit()
