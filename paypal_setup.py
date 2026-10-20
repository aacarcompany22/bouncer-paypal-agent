
import os
import requests
from dotenv import load_dotenv

load_dotenv()
BASE = os.getenv("PAYPAL_BASE_URL")


def get_token():
    r = requests.post(
        f"{BASE}/v1/oauth2/token",
        auth=(os.getenv("PAYPAL_CLIENT_ID"), os.getenv("PAYPAL_SECRET")),
        data={"grant_type": "client_credentials"},
    )
    r.raise_for_status()
    return r.json()["access_token"]


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