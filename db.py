
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
        # what the proactive AI watchdog decided about each event
        conn.execute(
            """CREATE TABLE IF NOT EXISTS agent_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT UNIQUE,
                created_at TEXT,
                status TEXT,
                headline TEXT,
                message TEXT,
                sub_id TEXT,
                action TEXT,
                reason TEXT
            )"""
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
        is_new = cur.rowcount > 0
        row = conn.execute(
            "SELECT service FROM subscriptions WHERE sub_id = ?", (sub_id,)
        ).fetchone()
    if is_new:
        try:
            import search_store

            search_store.index_event(
                event_id, event_type, sub_id, row["service"] if row else None, detail, now
            )
        except Exception as e:
            print("Elastic indexing skipped:", e)
    return is_new


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
def update_price_for_plan(plan_id, price):
    with connect() as conn:
        conn.execute("UPDATE subscriptions SET price = ? WHERE plan_id = ?", (price, plan_id))


# ---------- Proactive AI watchdog ----------
def max_event_id():
    with connect() as conn:
        row = conn.execute("SELECT MAX(id) AS m FROM events").fetchone()
    return row["m"] or 0


def events_after(last_id, limit=20):
    """Events newer than last_id, oldest first."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM events WHERE id > ? ORDER BY id ASC LIMIT ?", (last_id, limit)
        ).fetchall()
    return [dict(r) for r in rows]


def claim_agent_review(event_id):
    """Reserve an event for review. Returns False if it was already reviewed (or is being)."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    with connect() as conn:
        cur = conn.execute(
            "INSERT OR IGNORE INTO agent_alerts (event_id, created_at, status) VALUES (?, ?, 'thinking')",
            (event_id, now),
        )
    return cur.rowcount > 0


def finish_agent_review(event_id, status, headline=None, message=None,
                        sub_id=None, action=None, reason=None):
    with connect() as conn:
        conn.execute(
            "UPDATE agent_alerts SET status = ?, headline = ?, message = ?, sub_id = ?, "
            "action = ?, reason = ? WHERE event_id = ?",
            (status, headline, message, sub_id, action, reason, event_id),
        )


def list_agent_alerts(status="open", limit=3):
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM agent_alerts WHERE status = ? ORDER BY id DESC LIMIT ?", (status, limit)
        ).fetchall()
    return [dict(r) for r in rows]


def set_agent_alert_status(alert_id, status):
    with connect() as conn:
        conn.execute("UPDATE agent_alerts SET status = ? WHERE id = ?", (status, alert_id))