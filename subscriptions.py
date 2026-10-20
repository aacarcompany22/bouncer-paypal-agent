
import os
import sys
import requests
from dotenv import load_dotenv
from paypal_setup import headers

load_dotenv()
BASE = os.getenv("PAYPAL_BASE_URL")


def create_subscription(plan_id):
    body = {
        "plan_id": plan_id,
        "application_context": {
            "brand_name": "StreamFlix",
            "user_action": "SUBSCRIBE_NOW",
            "return_url": "https://example.com/success",
            "cancel_url": "https://example.com/cancel",
        },
    }
    r = requests.post(f"{BASE}/v1/billing/subscriptions", headers=headers(), json=body)
    print("Create:", r.status_code)
    r.raise_for_status()
    data = r.json()
    print("Subscription ID:", data["id"])
    print("Status:", data["status"])
    for link in data["links"]:
        if link["rel"] == "approve":
            print("\nOPEN THIS LINK AND APPROVE IT:")
            print(link["href"])


def get_subscription(sub_id):
    r = requests.get(f"{BASE}/v1/billing/subscriptions/{sub_id}", headers=headers())
    print("Get:", r.status_code)
    r.raise_for_status()
    data = r.json()
    print("Status:", data["status"])
    print("Plan:", data["plan_id"])
    billing = data.get("billing_info", {})
    print("Next billing time:", billing.get("next_billing_time"))


def cancel_subscription(sub_id):
    r = requests.post(
        f"{BASE}/v1/billing/subscriptions/{sub_id}/cancel",
        headers=headers(),
        json={"reason": "Cancelled by Bouncer"},
    )
    print("Cancel:", r.status_code)  # 204 means success
    r.raise_for_status()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python subscriptions.py create | status <id> | cancel <id>")
    elif sys.argv[1] == "create":
        create_subscription(os.getenv("STREAMFLIX_PLAN_ID"))
    elif sys.argv[1] == "status":
        get_subscription(sys.argv[2])
    elif sys.argv[1] == "cancel":
        cancel_subscription(sys.argv[2])