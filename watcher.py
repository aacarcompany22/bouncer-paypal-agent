"""Bouncer's proactive AI watchdog.

Every new event (PayPal webhooks, trial-ending warnings, price changes, pool updates) lands in the
events table. This job picks up the ones that can affect the user's money and lets the AI decide,
by itself, whether to alert the user and what to recommend. Nothing is ever paused or cancelled here:
recommendations wait in the app for the user to approve.
"""
import alerts
import assistant
import db

# events worth an AI review; user-initiated ones (Kill Switch, pause, cancel) are left alone
TRIGGERS = {
    "BOUNCER.TRIAL_ENDING",
    "BOUNCER.PRICE_CHANGE",
    "BOUNCER.ACCESS_REVOKED",
    "BILLING.SUBSCRIPTION.ACTIVATED",
    "BILLING.SUBSCRIPTION.PAYMENT.FAILED",
    "PAYMENT.SALE.COMPLETED",
    "PAYMENT.SALE.DENIED",
}
MAX_REVIEWS_PER_RUN = 3  # keeps a burst of events from using up the daily AI budget at once
CURSOR = "agent_last_event_id"


def run_watch():
    last = int(db.get_setting(CURSOR, "-1"))
    if last < 0:
        # first start: only watch what happens from now on, not the whole history
        db.set_setting(CURSOR, db.max_event_id())
        return

    reviewed = 0
    for event in db.events_after(last):
        if event["event_type"] in TRIGGERS:
            if reviewed >= MAX_REVIEWS_PER_RUN:
                return  # the rest waits for the next run
            if db.claim_agent_review(event["event_id"]):
                reviewed += 1
                review(event)
        db.set_setting(CURSOR, event["id"])


def review(event):
    names = {s["sub_id"]: s["service"] for s in db.list_subscriptions()}
    try:
        result = assistant.review_event(event, names.get(event["sub_id"]))
    except Exception as e:
        print("Watchdog review failed:", e)
        db.finish_agent_review(event["event_id"], "error")
        return

    if not result:
        db.finish_agent_review(event["event_id"], "quiet")
        print("Watchdog stayed quiet about", event["event_type"])
        return

    db.finish_agent_review(event["event_id"], "open", **result)
    service = names.get(result["sub_id"])
    db.add_event(f"AI-{event['event_id']}", "BOUNCER.AI_ALERT", result["sub_id"],
                 f"{result['headline']}: {result['message']}")
    ask = ""
    if result["action"]:
        ask = f" Recommends: {result['action']} {service or 'a subscription'}. Approve it in Bouncer."
    alerts.send_alert(f"Bouncer AI: {result['headline']}. {result['message']}{ask}")
    print("Watchdog alert:", result["headline"])
