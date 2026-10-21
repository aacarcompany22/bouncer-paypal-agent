
import sqlite3

DB_FILE = "bouncer.db"


def connect():
    conn = sqlite3.connect(DB_FILE)
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