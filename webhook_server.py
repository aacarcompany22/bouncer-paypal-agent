
import os

import requests
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request

import db
import paypal_api
from paypal_setup import headers

from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler

import alerts

load_dotenv()
BASE = os.getenv("PAYPAL_BASE_URL")
WEBHOOK_ID = os.getenv("WEBHOOK_ID")
VERIFY = os.getenv("WEBHOOK_VERIFY", "true").lower() == "true"

app = FastAPI()
db.init_db()


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

    # 2. Work out which subscription this is about
    if event_type.startswith("BILLING.SUBSCRIPTION"):
        sub_id = resource.get("id")
    else:
        sub_id = resource.get("billing_agreement_id")

    # 3. Build a readable description
    if event_type == "PAYMENT.SALE.COMPLETED":
        amount = resource.get("amount", {})
        detail = f"Payment of {amount.get('total')} {amount.get('currency')} completed"
    else:
        detail = event.get("summary", "")

        is_new = db.add_event(event_id, event_type, sub_id, detail)
    if is_new:
        names = {s["sub_id"]: s["service"] for s in db.list_subscriptions()}
        alerts.send_alert(
            f"🛡️ Bouncer: {event_type} for {names.get(sub_id, 'unknown service')}. {detail}"
        )
    print("Received:", event_type, sub_id)

    # 4. Sync our database with PayPal's current truth
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
    stages = sorted({x for x in (window, 3, 1) if x <= window})  # e.g. 7 -> 1, 3, 7
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
            alerts.send_alert(f"🚨 Hold up! {msg}. Open Bouncer to pause or cancel it.")


scheduler = BackgroundScheduler()
scheduler.add_job(check_trials, "interval", minutes=1)
scheduler.start()