
import json
import os

import requests
from dotenv import load_dotenv

from paypal_setup import headers

load_dotenv()
BASE = os.getenv("PAYPAL_BASE_URL")

with open("services.json") as f:
    services = json.load(f)

for name, info in services.items():
    r = requests.get(f"{BASE}/v1/billing/plans/{info['plan_id']}", headers=headers())
    if not r.ok:
        print(name, "->", r.status_code, r.text[:200])
        continue
    d = r.json()
    cycles = [
        (c["tenure_type"], c.get("pricing_scheme", {}).get("fixed_price", {}).get("value"))
        for c in d["billing_cycles"]
    ]
    print(f"{name}: status={d['status']}  cycles={cycles}")