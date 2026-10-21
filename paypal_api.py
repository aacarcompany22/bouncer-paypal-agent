
import os
import requests
from dotenv import load_dotenv
from paypal_setup import headers

load_dotenv()
BASE = os.getenv("PAYPAL_BASE_URL")


def create_subscription(plan_id, brand="Bouncer Demo"):
    body = {
        "plan_id": plan_id,
        "application_context": {
            "brand_name": brand,
            "user_action": "SUBSCRIBE_NOW",
            "return_url": "https://example.com/success",
            "cancel_url": "https://example.com/cancel",
        },
    }
    r = requests.post(f"{BASE}/v1/billing/subscriptions", headers=headers(), json=body)
    r.raise_for_status()
    data = r.json()
    approve_url = next((l["href"] for l in data["links"] if l["rel"] == "approve"), None)
    return data["id"], approve_url


def get_subscription(sub_id):
    r = requests.get(f"{BASE}/v1/billing/subscriptions/{sub_id}", headers=headers())
    r.raise_for_status()
    return r.json()


def cancel_subscription(sub_id):
    r = requests.post(
        f"{BASE}/v1/billing/subscriptions/{sub_id}/cancel",
        headers=headers(),
        json={"reason": "Cancelled by Bouncer"},
    )
    r.raise_for_status()
def suspend_subscription(sub_id):
    r = requests.post(
        f"{BASE}/v1/billing/subscriptions/{sub_id}/suspend",
        headers=headers(),
        json={"reason": "Paused by Bouncer"},
    )
    r.raise_for_status()


def activate_subscription(sub_id):
    r = requests.post(
        f"{BASE}/v1/billing/subscriptions/{sub_id}/activate",
        headers=headers(),
        json={"reason": "Resumed by Bouncer"},
    )
    r.raise_for_status()


def list_transactions(sub_id):
    r = requests.get(
        f"{BASE}/v1/billing/subscriptions/{sub_id}/transactions",
        headers=headers(),
        params={
            "start_time": "2026-01-01T00:00:00.000Z",
            "end_time": "2027-12-31T23:59:59.000Z",
        },
    )
    r.raise_for_status()
    return r.json().get("transactions", [])  