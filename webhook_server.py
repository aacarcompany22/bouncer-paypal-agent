import os
from datetime import datetime, timezone

import requests
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request

import alerts
import db
import paypal_api
import pools
from paypal_setup import headers

load_dotenv()
BASE = os.getenv("PAYPAL_BASE_URL")
WEBHOOK_ID = os.getenv("WEBHOOK_ID")
VERIFY = os.getenv("WEBHOOK_VERIFY", "true").lower() == "true"

app = FastAPI()
db.init_db()
pools.init()


def verify_signature(req_headers, event):
    """Ask PayPal to confirm this event really came from PayPal."""
    body = {
        "auth_algo": req_headers.get("paypal-auth-algo"),
        "cert_url": req_headers.get("paypal-cert-url"),
        "transmission_id": req_headers.get("paypal-transmission-id"),
        "transmission_sig": req_headers.get("paypal-transmission-sig"),
        "transmission_time": req_headers.get("paypal-transmission-time"),
        "webhook_id": WEBHOOK_ID,
        "webhook_event": event,
    }
    r = requests.post(
        f"{BASE}/v1/notifications/verify-webhook-signature",
        headers=headers(),
        json=body,
    )
    r.raise_for_status()
    return r.json().get("verification_status") == "SUCCESS"


def handle_pool_payment(event_id, event_type, order_id):
    """A pool member approved or paid. Returns False if this order isn't a pool payment."""
    member = pools.get_member_by_order(order_id)
    if not member:
        return False
    pool = pools.get_pool(member["pool_id"])
    db.add_event(event_id, event_type, pool["sub_id"],
                 f"{member['name']}'s pool payment: {event_type}")
    try:
        msg = pools.sync_member(member)  # captures the payment if it was only approved
    except Exception as e:
        print("Pool sync failed:", e)
        return True
    if msg and db.add_event(f"SHARE-PAID-{member['id']}", "BOUNCER.SHARE_PAID", pool["sub_id"], msg):
        alerts.send_alert(f"Pool '{pool['name']}': {msg}")
        if pools.pool_funded(pool["id"]):
            done = f"Pool '{pool['name']}' is fully funded. Every share has been paid."
            if db.add_event(f"POOL-FUNDED-{pool['id']}", "BOUNCER.POOL_FUNDED", pool["sub_id"], done):
                alerts.send_alert(done)
    print("Pool payment handled:", member["name"])
    return True


@app.get("/")
def health():
    return {"status": "Bouncer webhook server is running"}


@app.post("/webhook")
async def webhook(request: Request):
    event = await request.json()
    event_type = event.get("event_type", "unknown")
    event_id = event.get("id")
    resource = event.get("resource", {})

    # 1. Security: reject anything PayPal didn't sign
    if VERIFY:
        try:
            ok = verify_signature(request.headers, event)
        except Exception as e:
            print("Signature check error:", e)
            ok = False
        if not ok:
            print("REJECTED event (bad signature):", event_type)
            raise HTTPException(status_code=400, detail="Invalid signature")

    # 2. Shared pool payments
    order_id = None
    if event_type == "CHECKOUT.ORDER.APPROVED":
        order_id = resource.get("id")
    elif event_type.startswith("PAYMENT.CAPTURE"):
        order_id = resource.get("supplementary_data", {}).get("related_ids", {}).get("order_id")
    if order_id and handle_pool_payment(event_id, event_type, order_id):
        return {"ok": True}

    # 3. Subscription events
    if event_type.startswith("BILLING.SUBSCRIPTION"):
        sub_id = resource.get("id")
    else:
        sub_id = resource.get("billing_agreement_id")

    if event_type == "PAYMENT.SALE.COMPLETED":
        amount = resource.get("amount", {})
        detail = f"Payment of {amount.get('total')} {amount.get('currency')} completed"
    else:
        detail = event.get("summary", "")

    is_new = db.add_event(event_id, event_type, sub_id, detail)
    if is_new:
        names = {s["sub_id"]: s["service"] for s in db.list_subscriptions()}
        alerts.send_alert(
            f"Bouncer: {event_type} for {names.get(sub_id, 'unknown service')}. {detail}"
        )
    print("Received:", event_type, sub_id)

    if sub_id:
        try:
            data = paypal_api.get_subscription(sub_id)
            billing = data.get("billing_info", {})
            db.update_subscription(sub_id, data["status"], billing.get("next_billing_time"))
        except Exception as e:
            print("Could not sync subscription:", e)

    return {"ok": True}


def check_trials():
    """Every minute, send staged reminders before a subscription starts charging."""
    window = int(db.get_setting("alert_days", os.getenv("TRIAL_ALERT_DAYS", "3")))
    stages = sorted({x for x in (window, 3, 1) if x <= window})
    for s in db.list_subscriptions():
        if s["status"] != "ACTIVE" or not s["next_billing_time"]:
            continue
        dt = datetime.fromisoformat(s["next_billing_time"].replace("Z", "+00:00"))
        days = (dt - datetime.now(timezone.utc)).days
        if days < 0 or days > window:
            continue
        stage = min(x for x in stages if days <= x)
        key = f"TRIAL-{s['sub_id']}-{s['next_billing_time']}-{stage}"
        when = "today" if days == 0 else f"in {days} day(s)"
        msg = f"{s['service']} will charge ${s['price']:.2f} {when}"
        if db.add_event(key, "BOUNCER.TRIAL_ENDING", s["sub_id"], msg):
            alerts.send_alert(f"Hold up! {msg}. Open Bouncer to pause or cancel it.")


def check_pools():
    """Every minute: revoke access after missed deadlines and send due-soon reminders."""
    for msg in pools.enforce_deadlines():
        alerts.send_alert(f"Access revoked: {msg}")
    for detail, url in pools.due_soon_reminders():
        alerts.send_alert(f"Reminder: {detail} Pay here: {url}")


scheduler = BackgroundScheduler()
scheduler.add_job(check_trials, "interval", minutes=1)
scheduler.add_job(check_pools, "interval", minutes=1)
scheduler.start()