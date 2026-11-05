
import json

import db

subs = [
    {"sub_id": s["sub_id"], "service": s["service"]}
    for s in db.list_subscriptions()
    if s["status"] in ("ACTIVE", "SUSPENDED")
]
with open("demo_subs.json", "w") as f:
    json.dump(subs, f, indent=2)
print(f"Saved {len(subs)} subscription(s) to demo_subs.json")
for s in subs:
    print("  ", s["service"], s["sub_id"])