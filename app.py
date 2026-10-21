
import json
from datetime import datetime, timezone

import streamlit as st

import db
import paypal_api

st.set_page_config(page_title="Bouncer", page_icon="🛡️", layout="wide")
db.init_db()

with open("services.json") as f:
    SERVICES = json.load(f)


def days_until(ts):
    if not ts:
        return None
    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    return (dt - datetime.now(timezone.utc)).days


def refresh_all():
    for sub in db.list_subscriptions():
        if sub["status"] == "CANCELLED":
            continue
        try:
            data = paypal_api.get_subscription(sub["sub_id"])
            billing = data.get("billing_info", {})
            db.update_subscription(
                sub["sub_id"], data["status"], billing.get("next_billing_time")
            )
        except Exception as e:
            st.warning(f"Could not refresh {sub['service']}: {e}")


st.title("🛡️ Bouncer")
st.caption("Your PayPal subscription guard. Sandbox mode: no real money moves.")

# ---------- Sidebar: add a subscription ----------
with st.sidebar:
    st.header("Add a subscription")
    service = st.selectbox("Service", list(SERVICES.keys()))
    info = SERVICES[service]
    st.caption(f"7-day free trial, then ${info['price']}/month")
    if st.button("Subscribe", type="primary"):
        try:
            sub_id, approve_url = paypal_api.create_subscription(
                info["plan_id"], brand=service
            )
            db.add_subscription(
                sub_id, service, info["plan_id"], info["price"],
                "APPROVAL_PENDING", approve_url,
            )
            st.success("Created. Approve it with your sandbox Personal account.")
        except Exception as e:
            st.error(f"Could not create subscription: {e}")

# ---------- Main area ----------
if st.button("🔄 Refresh from PayPal"):
    refresh_all()
    st.rerun()

subs = db.list_subscriptions()
active = [s for s in subs if s["status"] == "ACTIVE"]

col1, col2, col3 = st.columns(3)
col1.metric("Active subscriptions", len(active))
col2.metric("Monthly cost once trials end", f"${sum(s['price'] for s in active):.2f}")
col3.metric("Cancelled", len([s for s in subs if s["status"] == "CANCELLED"]))

# Trial alerts
for s in active:
    d = days_until(s["next_billing_time"])
    if d is not None and d <= 3:
        st.warning(f"⚠️ {s['service']} will start charging ${s['price']:.2f} in {d} day(s).")

st.divider()

if not subs:
    st.info("No subscriptions yet. Add one from the sidebar.")

for s in subs:
    c1, c2, c3, c4, c5 = st.columns([2, 1.5, 1.5, 2, 2])
    c1.write(f"**{s['service']}**")
    c2.write(f"${s['price']:.2f}/month")
    c3.write(s["status"])

    d = days_until(s["next_billing_time"])
    c4.write(f"Next charge in {d} day(s)" if d is not None else "-")

    if s["status"] == "APPROVAL_PENDING" and s["approve_url"]:
        c5.link_button("Approve in PayPal", s["approve_url"])
    elif s["status"] in ("ACTIVE", "APPROVED"):
        if c5.button("Cancel", key=f"cancel_{s['sub_id']}"):
            try:
                paypal_api.cancel_subscription(s["sub_id"])
                db.update_subscription(s["sub_id"], "CANCELLED", None)
                st.rerun()
            except Exception as e:
                st.error(f"Cancel failed: {e}")