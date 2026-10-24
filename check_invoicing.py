
import os

import requests
from dotenv import load_dotenv

load_dotenv()
BASE = os.getenv("PAYPAL_BASE_URL")

r = requests.post(
    f"{BASE}/v1/oauth2/token",
    auth=(os.getenv("PAYPAL_CLIENT_ID"), os.getenv("PAYPAL_SECRET")),
    data={"grant_type": "client_credentials"},
)
data = r.json()
print("Token status:", r.status_code)
scopes = data.get("scope", "").split()
print("Invoicing permission granted:", any("invoicing" in s for s in scopes))
print("Granted scopes:")
for s in scopes:
    print("   ", s)

token = data["access_token"]
t = requests.get(
    f"{BASE}/v2/invoicing/invoices",
    params={"page": 1, "page_size": 1},
    headers={"Authorization": f"Bearer {token}"},
)
print("\nList invoices:", t.status_code)
print(t.text[:300])
print("\nBusiness email in .env:", os.getenv("PAYPAL_BUSINESS_EMAIL"))