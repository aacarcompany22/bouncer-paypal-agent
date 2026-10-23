
import sqlite3
from datetime import datetime, timezone

DB_FILE = "bouncer.db"


def connect():
    conn = sqlite3.connect(DB_FILE, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with connect() as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS subscriptions (
                sub_id TEXT PRIMARY KEY,
                service TEXT,
                plan_id TEXT,
                price REAL,
                status TEXT,
                next_billing_time TEXT,
                approve_url TEXT
            )"""
        )
        conn.execute(
            """CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT UNIQUE,
                event_type TEXT,
                sub_id TEXT,
                detail TEXT,
                received_at TEXT
            )"""
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)"
        )


def add_subscription(sub_id, service, plan_id, price, status, approve_url):
    with connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO subscriptions VALUES (?, ?, ?, ?, ?, NULL, ?)",
            (sub_id, service, plan_id, price, status, approve_url),
        )


def update_subscription(sub_id, status, next_billing_time):
    with connect() as conn:
        conn.execute(
            "UPDATE subscriptions SET status = ?, next_billing_time = ? WHERE sub_id = ?",
            (status, next_billing_time, sub_id),
        )


def list_subscriptions():
    with connect() as conn:
        rows = conn.execute("SELECT * FROM subscriptions").fetchall()
    return [dict(r) for r in rows]


def add_event(event_id, event_type, sub_id, detail):
    """Returns True if the event was new, False if it was a duplicate."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    with connect() as conn:
        cur = conn.execute(
            "INSERT OR IGNORE INTO events (event_id, event_type, sub_id, detail, received_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (event_id, event_type, sub_id, detail, now),
        )
        return cur.rowcount > 0


def list_events(limit=15):
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM events ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


def get_setting(key, default=None):
    with connect() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def set_setting(key, value):
    with connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value))
        )