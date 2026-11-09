"""Bouncer Autopilot: a standing rule the user switches on once.

While it is on, Bouncer pauses a free trial through PayPal before it starts charging, without
waiting to be asked, and then reports what it did. It only ever pauses (which can be undone with
Resume) and never cancels. It acts once per subscription, so a trial the user resumes stays resumed.
"""
import os
from datetime import datetime, timezone

import alerts
import db
import paypal_api


def enabled():
    return db.get_setting("autopilot", "0") == "1"


def _still_in_trial(data):
    """True if PayPal shows no paid billing cycle has completed yet."""
    cycles = data.get("billing_info", {}).get("cycle_executions", [])
    regular = [c for c in cycles if c.get("tenure_type") == "REGULAR"]
    return bool(regular) and all(c.get("cycles_completed", 0) == 0 for c in regular)


def run():
    """Pause every trial inside the user's warning window. Returns how many were paused."""
    if not enabled():
        return 0
    window = int(db.get_setting("alert_days", os.getenv("TRIAL_ALERT_DAYS", "3")))
    paused = 0
    for s in db.list_subscriptions():
        if s["status"] != "ACTIVE" or not s["next_billing_time"]:
            continue
        dt = datetime.fromisoformat(s["next_billing_time"].replace("Z", "+00:00"))
        days = (dt - datetime.now(timezone.utc)).days
        if days < 0 or days > window:
            continue
        key = f"AUTOPILOT-{s['sub_id']}"
        if not db.claim_agent_review(key):
            continue  # Autopilot already acted on this one; the user's later choice stands
        try:
            data = paypal_api.get_subscription(s["sub_id"])  # check PayPal's facts before acting
            if data.get("status") != "ACTIVE" or not _still_in_trial(data):
                db.finish_agent_review(key, "quiet")
                continue
            paypal_api.suspend_subscription(s["sub_id"])
        except Exception as e:
            print("Autopilot could not pause", s["sub_id"], e)
            db.release_agent_review(key)  # try again on the next run
            continue

        db.update_subscription(s["sub_id"], "SUSPENDED", None)
        when = "today" if days == 0 else f"in {days} day(s)"
        yearly = s["price"] * 12
        headline = f"Autopilot paused {s['service']}"
        message = (f"Its free trial was about to start charging ${s['price']:.2f}/month {when}. "
                   f"Bouncer paused it with PayPal under your Autopilot rule, so nothing is charged. "
                   f"That protects ${yearly:.2f} a year until you decide.")
        db.finish_agent_review(key, "open", headline=headline, message=message,
                               sub_id=s["sub_id"], action="resume",
                               reason="Paused, not cancelled. You can resume it any time.")
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        db.add_event(f"{key}-{stamp}", "BOUNCER.AUTOPILOT", s["sub_id"],
                     f"Autopilot paused {s['service']} before its trial charged "
                     f"${s['price']:.2f} {when}.")
        alerts.send_alert(f"Bouncer Autopilot: paused {s['service']} before it charged "
                          f"${s['price']:.2f} {when}. Resume it in Bouncer if you want to keep it.")
        paused += 1
    return paused
