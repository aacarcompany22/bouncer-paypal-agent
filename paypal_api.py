
import os
from datetime import datetime, timedelta, timezone

import requests
from dotenv import load_dotenv
from paypal_setup import TIMEOUT, app_url, headers

load_dotenv()
BASE = os.getenv("PAYPAL_BASE_URL")


def create_subscription(plan_id, brand="Bouncer Demo"):
    body = {
        "plan_id": plan_id,
        "application_context": {
            "brand_name": brand,
            "user_action": "SUBSCRIBE_NOW",
            "return_url": f"{app_url()}/?approved=1",
            "cancel_url": f"{app_url()}/?cancelled=1",
        },
    }
    r = requests.post(f"{BASE}/v1/billing/subscriptions", headers=headers(), json=body, timeout=TIMEOUT)
    r.raise_for_status()
    data = r.json()
    approve_url = next((l["href"] for l in data["links"] if l["rel"] == "approve"), None)
    return data["id"], approve_url


def get_subscription(sub_id):
    r = requests.get(f"{BASE}/v1/billing/subscriptions/{sub_id}", headers=headers(), timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def cancel_subscription(sub_id):
    r = requests.post(
        f"{BASE}/v1/billing/subscriptions/{sub_id}/cancel",
        headers=headers(),
        json={"reason": "Cancelled by Bouncer"},
        timeout=TIMEOUT,
    )
    r.raise_for_status()
def suspend_subscription(sub_id):
    r = requests.post(
        f"{BASE}/v1/billing/subscriptions/{sub_id}/suspend",
        headers=headers(),
        json={"reason": "Paused by Bouncer"},
        timeout=TIMEOUT,
    )
    r.raise_for_status()


def activate_subscription(sub_id):
    r = requests.post(
        f"{BASE}/v1/billing/subscriptions/{sub_id}/activate",
        headers=headers(),
        json={"reason": "Resumed by Bouncer"},
        timeout=TIMEOUT,
    )
    r.raise_for_status()


def list_transactions(sub_id):
    now = datetime.now(timezone.utc)
    r = requests.get(
        f"{BASE}/v1/billing/subscriptions/{sub_id}/transactions",
        headers=headers(),
        params={
            # PayPal needs a window: the last two years up to now
            "start_time": (now - timedelta(days=730)).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "end_time": now.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        },
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    return r.json().get("transactions", [])  
def update_plan_price(plan_id, new_price, billing_cycle_sequence=2):
    """Change the price of a plan's paid (REGULAR) billing cycle. PayPal returns 204 on success."""
    body = {
        "pricing_schemes": [
            {
                "billing_cycle_sequence": billing_cycle_sequence,
                "pricing_scheme": {
                    "fixed_price": {"value": f"{new_price:.2f}", "currency_code": "USD"}
                },
            }
        ]
    }
    r = requests.post(
        f"{BASE}/v1/billing/plans/{plan_id}/update-pricing-schemes",
        headers=headers(),
        json=body,
        timeout=TIMEOUT,
    )
    if not r.ok:
        raise RuntimeError(f"PayPal said {r.status_code}: {r.text}")