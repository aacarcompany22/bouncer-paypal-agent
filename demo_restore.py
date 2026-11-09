
import json
import os
from datetime import datetime, timedelta, timezone

import requests
from dotenv import load_dotenv

import db
import paypal_api
from paypal_setup import TIMEOUT, headers

load_dotenv()
BASE = os.getenv("PAYPAL_BASE_URL")
PATH = "demo_subs.json"


def discover_from_webhooks(days=30, max_pages=5):
    """Find subscription IDs in PayPal's recent webhook event history."""
    start = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    url = f"{BASE}/v1/notifications/webhooks-events"
    params = {"page_size": 100, "start_time": start}
    found = []
    for _ in range(max_pages):
        r = requests.get(url, headers=headers(), params=params, timeout=TIMEOUT)
        if not r.ok and params and "page_size" in params:
            params = {k: v for k, v in params.items() if k != "page_size"}
            r = requests.get(url, headers=headers(), params=params, timeout=TIMEOUT)
        if not r.ok:
            print("Could not read webhook history:", r.status_code, r.text[:200])
            break
        body = r.json()
        for ev in body.get("events", []):
            if not str(ev.get("event_type", "")).startswith("BILLING.SUBSCRIPTION"):
                continue
            sid = (ev.get("resource") or {}).get("id")
            if isinstance(sid, str) and sid.startswith("I-") and sid not in found:
                found.append(sid)
        nxt = next((l["href"] for l in body.get("links", []) if l.get("rel") == "next"), None)
        if not nxt:
            break
        url, params = nxt, None
    return found


def plan_info(plan_id):
    """Look up a plan's name and monthly price from PayPal."""
    r = requests.get(f"{BASE}/v1/billing/plans/{plan_id}", headers=headers(), timeout=TIMEOUT)
    if not r.ok:
        return "Subscription", 0.0
    d = r.json()
    price = 0.0
    for c in d.get("billing_cycles", []):
        if c.get("tenure_type") == "REGULAR":
            price = float(c["pricing_scheme"]["fixed_price"]["value"])
    return d.get("name", "Subscription").split(" Monthly")[0], price


def restore():
    db.init_db()
    wanted = []
    if os.path.exists(PATH):
        with open(PATH) as f:
            wanted = [item["sub_id"] for item in json.load(f)]
    try:
        for sid in discover_from_webhooks():
            if sid not in wanted:
                wanted.append(sid)
    except Exception as e:
        print("Webhook discovery skipped:", e)

    with open("services.json") as f:
        services = json.load(f)
    by_plan = {info["plan_id"]: (name, info["price"]) for name, info in services.items()}
    have = {s["sub_id"] for s in db.list_subscriptions()}

    restored = 0
    for sub_id in wanted:
        if sub_id in have:
            continue
        try:
            data = paypal_api.get_subscription(sub_id)
        except Exception as e:
            print(f"Could not restore {sub_id}: {e}")
            continue
        status = data.get("status")
        if status not in ("ACTIVE", "SUSPENDED"):
            continue
        plan_id = data.get("plan_id")
        name, price = by_plan.get(plan_id) or plan_info(plan_id)
        db.add_subscription(sub_id, name, plan_id, price, status, None)
        db.update_subscription(sub_id, status, data.get("billing_info", {}).get("next_billing_time"))
        restored += 1
    print(f"Restored {restored} subscription(s) from PayPal.")
    return restored


if __name__ == "__main__":
    restore()