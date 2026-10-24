
import os
import time
from datetime import date, timedelta

import requests
from dotenv import load_dotenv

import db
from paypal_setup import headers

load_dotenv()
BASE = os.getenv("PAYPAL_BASE_URL")
BUSINESS_EMAIL = os.getenv("PAYPAL_BUSINESS_EMAIL")
PAID_STATES = {"PAID", "MARKED_AS_PAID"}


def init():
    with db.connect() as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS pools (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sub_id TEXT, name TEXT, total REAL, due_date TEXT
            )"""
        )
        conn.execute(
            """CREATE TABLE IF NOT EXISTS pool_members (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pool_id INTEGER, name TEXT, email TEXT, share REAL,
                invoice_id TEXT, pay_url TEXT,
                status TEXT, access TEXT
            )"""
        )


def create_pool(sub_id, name, total, due_days, people):
    """people = [(name, email), ...]. The split is equal between you and the members."""
    share = round(total / (len(people) + 1), 2)
    due = (date.today() + timedelta(days=due_days)).isoformat()
    with db.connect() as conn:
        cur = conn.execute(
            "INSERT INTO pools (sub_id, name, total, due_date) VALUES (?, ?, ?, ?)",
            (sub_id, name, total, due),
        )
        pool_id = cur.lastrowid
        for person, email in people:
            conn.execute(
                "INSERT INTO pool_members (pool_id, name, email, share, status, access) "
                "VALUES (?, ?, ?, ?, 'NOT_REQUESTED', 'PENDING')",
                (pool_id, person, email, share),
            )
    return pool_id


def list_pools():
    with db.connect() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM pools ORDER BY id DESC")]


def list_members(pool_id):
    with db.connect() as conn:
        rows = conn.execute("SELECT * FROM pool_members WHERE pool_id = ?", (pool_id,)).fetchall()
    return [dict(r) for r in rows]

def request_payment(member_id):
    """Create a PayPal order for one member's share and return the link they approve."""
    with db.connect() as conn:
        m = conn.execute(
            "SELECT m.*, p.name AS pool_name FROM pool_members m "
            "JOIN pools p ON p.id = m.pool_id WHERE m.id = ?",
            (member_id,),
        ).fetchone()
    m = dict(m)

    body = {
        "intent": "CAPTURE",
        "purchase_units": [
            {
                "reference_id": f"member-{member_id}",
                "description": f"{m['name']}'s share of the {m['pool_name']} pool",
                "amount": {"currency_code": "USD", "value": f"{m['share']:.2f}"},
            }
        ],
        "payment_source": {
            "paypal": {
                "experience_context": {
                    "brand_name": "Bouncer Pools",
                    "user_action": "PAY_NOW",
                    "return_url": "https://example.com/paid",
                    "cancel_url": "https://example.com/cancelled",
                }
            }
        },
    }
    h = headers()
    h["PayPal-Request-Id"] = f"bouncer-pool-member-{member_id}"  # stops duplicate orders
    r = requests.post(f"{BASE}/v2/checkout/orders", headers=h, json=body)
    if not r.ok:
        raise RuntimeError(f"PayPal said {r.status_code}: {r.text}")
    data = r.json()
    order_id = data["id"]
    pay_url = next(
        (l["href"] for l in data.get("links", []) if l.get("rel") in ("payer-action", "approve")),
        None,
    )
    with db.connect() as conn:
        # the invoice_id column now holds the PayPal order id
        conn.execute(
            "UPDATE pool_members SET invoice_id = ?, pay_url = ?, status = 'UNPAID' WHERE id = ?",
            (order_id, pay_url, member_id),
        )
    return pay_url


def sync_member(m):
    """Check whether the member approved their payment, capture it, and update access."""
    if not m["invoice_id"]:
        return
    r = requests.get(f"{BASE}/v2/checkout/orders/{m['invoice_id']}", headers=headers())
    if not r.ok:
        raise RuntimeError(f"PayPal said {r.status_code}: {r.text}")
    state = r.json().get("status", "")

    if state == "APPROVED":  # the payer has approved, so Bouncer collects the money now
        c = requests.post(
            f"{BASE}/v2/checkout/orders/{m['invoice_id']}/capture",
            headers=headers(),
            json={},
        )
        if not c.ok:
            raise RuntimeError(f"PayPal said {c.status_code}: {c.text}")
        state = c.json().get("status", state)

    if state == "COMPLETED":
        status, access = "PAID", "ACTIVE"
    elif state == "VOIDED":
        status, access = "CANCELLED", m["access"]
    else:
        status = "UNPAID"
        access = "REVOKED" if m["access"] == "REVOKED" else "PENDING"
    with db.connect() as conn:
        conn.execute(
            "UPDATE pool_members SET status = ?, access = ? WHERE id = ?", (status, access, m["id"])
        )

def sync_pool(pool_id):
    for m in list_members(pool_id):
        sync_member(m)