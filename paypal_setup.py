
import os
import time

import requests
from dotenv import load_dotenv

load_dotenv()
BASE = os.getenv("PAYPAL_BASE_URL")
TIMEOUT = 20  # seconds; stops the app hanging if PayPal is slow
_token = {"value": None, "expires": 0.0}


def app_url():
    """Where PayPal sends people back after approving. Render sets RENDER_EXTERNAL_URL itself."""
    return (os.getenv("APP_URL") or os.getenv("RENDER_EXTERNAL_URL")
            or "http://localhost:8501").rstrip("/")


def get_token():
    # PayPal tokens last for hours, so reuse one until shortly before it expires
    if _token["value"] and time.time() < _token["expires"] - 60:
        return _token["value"]
    r = requests.post(
        f"{BASE}/v1/oauth2/token",
        auth=(os.getenv("PAYPAL_CLIENT_ID"), os.getenv("PAYPAL_SECRET")),
        data={"grant_type": "client_credentials"},
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    data = r.json()
    _token["value"] = data["access_token"]
    _token["expires"] = time.time() + int(data.get("expires_in", 300))
    return _token["value"]


def headers():
    return {
        "Authorization": f"Bearer {get_token()}",
        "Content-Type": "application/json",
    }


def create_product(name, description):
    r = requests.post(
        f"{BASE}/v1/catalogs/products",
        headers=headers(),
        json={
            "name": name,
            "description": description,
            "type": "SERVICE",
            "category": "SOFTWARE",
        },
    )
    print("Product:", r.status_code)
    print(r.text)
    r.raise_for_status()
    return r.json()["id"]


def create_trial_plan(product_id, name, monthly_price):
    body = {
        "product_id": product_id,
        "name": name,
        "description": f"{name}: 7-day free trial, then monthly billing",
        "status": "ACTIVE",
        "billing_cycles": [
            {
                "frequency": {"interval_unit": "DAY", "interval_count": 7},
                "tenure_type": "TRIAL",
                "sequence": 1,
                "total_cycles": 1,
            },
            {
                "frequency": {"interval_unit": "MONTH", "interval_count": 1},
                "tenure_type": "REGULAR",
                "sequence": 2,
                "total_cycles": 0,
                "pricing_scheme": {
                    "fixed_price": {"value": str(monthly_price), "currency_code": "USD"}
                },
            },
        ],
        "payment_preferences": {
            "auto_bill_outstanding": True,
            "setup_fee_failure_action": "CONTINUE",
            "payment_failure_threshold": 3,
        },
    }
    r = requests.post(f"{BASE}/v1/billing/plans", headers=headers(), json=body)
    print("Plan:", r.status_code)
    print(r.text)
    r.raise_for_status()
    return r.json()["id"]


if __name__ == "__main__":
    product_id = create_product("StreamFlix", "Demo streaming service")
    plan_id = create_trial_plan(product_id, "StreamFlix Monthly", 9.99)
    print("\nSAVE THESE:")
    print("PRODUCT_ID =", product_id)
    print("PLAN_ID    =", plan_id)