
import json
from datetime import datetime, timezone

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

import ai
import db
import paypal_api
import ui
import assistant 

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
            db.update_subscription(sub["sub_id"], data["status"], billing.get("next_billing_time"))
        except Exception as e:
            st.warning(f"Could not refresh {sub['service']}: {e}")


st.title("🛡️ Bouncer")
st.caption("The bouncer for your PayPal subscriptions. Sandbox mode: no real money moves.")

# ---------- Sidebar ----------
with st.sidebar:
    st.header("Add a subscription")
    service = st.selectbox("Service", list(SERVICES.keys()))
    info = SERVICES[service]
    st.caption(f"7-day free trial, then ${info['price']}/month")
    if st.button("Subscribe", type="primary"):
        try:
            sub_id, approve_url = paypal_api.create_subscription(info["plan_id"], brand=service)
            db.add_subscription(sub_id, service, info["plan_id"], info["price"],
                                "APPROVAL_PENDING", approve_url)
            st.success("Created. Approve it with your sandbox Personal account.")
        except Exception as e:
            st.error(f"Could not create subscription: {e}")

subs = db.list_subscriptions()
active = [s for s in subs if s["status"] == "ACTIVE"]

# ---------- Bouncer ----------
alert_msg = None
for s in active:
    d = days_until(s["next_billing_time"])
    if d is not None and d <= 3:
        alert_msg = f"Hold up! {s['service']} starts charging ${s['price']:.2f} in {d} day(s)."
        break

if alert_msg:
    components.html(ui.bouncer_html(alert_msg, alert=True), height=250)
elif active:
    components.html(ui.bouncer_html(f"All clear, boss. I'm watching {len(active)} subscription(s).", False), height=250)
else:
    components.html(ui.bouncer_html("Nobody's on the list yet. Add a subscription.", False), height=250)

if st.button("🔄 Refresh from PayPal"):
    refresh_all()
    st.rerun()

# ---------- Metrics and charts ----------
c1, c2, c3 = st.columns(3)
c1.metric("Active subscriptions", len(active))
c2.metric("Monthly cost once trials end", f"${sum(s['price'] for s in active):.2f}")
c3.metric("Cancelled", len([s for s in subs if s["status"] == "CANCELLED"]))

if subs:
    left, right = st.columns(2)
    left.plotly_chart(ui.subscription_map(subs), use_container_width=True)
    right.plotly_chart(ui.spend_donut(subs), use_container_width=True)

st.divider()

# ---------- Subscription list ----------
for s in subs:
    c1, c2, c3, c4, c5 = st.columns([2, 1.3, 1.6, 2, 3])
    c1.write(f"**{s['service']}**")
    c2.write(f"${s['price']:.2f}/month")
    c3.write(s["status"])
    d = days_until(s["next_billing_time"])
    c4.write(f"Next charge in {d} day(s)" if d is not None else "-")

    if s["status"] == "APPROVAL_PENDING" and s["approve_url"]:
        c5.link_button("Approve in PayPal", s["approve_url"])
    elif s["status"] in ("ACTIVE", "SUSPENDED"):
        b1, b2 = c5.columns(2)
        if s["status"] == "ACTIVE":
            if b1.button("⏸ Pause", key=f"pause_{s['sub_id']}"):
                try:
                    paypal_api.suspend_subscription(s["sub_id"])
                    db.update_subscription(s["sub_id"], "SUSPENDED", None)
                    st.rerun()
                except Exception as e:
                    st.error(f"Pause failed: {e}")
        else:
            if b1.button("▶ Resume", key=f"resume_{s['sub_id']}"):
                try:
                    paypal_api.activate_subscription(s["sub_id"])
                    refresh_all()
                    st.rerun()
                except Exception as e:
                    st.error(f"Resume failed: {e}")
        if b2.button("🚫 Cancel", key=f"cancel_{s['sub_id']}"):
            try:
                paypal_api.cancel_subscription(s["sub_id"])
                db.update_subscription(s["sub_id"], "CANCELLED", None)
                st.rerun()
            except Exception as e:
                st.error(f"Cancel failed: {e}")

# ---------- Payment history ----------
st.divider()
st.subheader("💳 Payment history from PayPal")
if subs:
    labels = {f"{s['service']} ({s['sub_id']})": s["sub_id"] for s in subs}
    choice = st.selectbox("Subscription", list(labels.keys()))
    if st.button("Load payment history"):
        try:
            txs = paypal_api.list_transactions(labels[choice])
            if not txs:
                st.info("No charges yet. That's expected during the free trial.")
            else:
                st.dataframe(pd.DataFrame([{
                    "Time": t.get("time"),
                    "Status": t.get("status"),
                    "Amount": t.get("amount_with_breakdown", {}).get("gross_amount", {}).get("value"),
                } for t in txs]))
        except Exception as e:
            st.error(f"Could not load history: {e}")

# ---------- AI advice ----------
st.divider()
st.subheader("🤖 Bouncer AI advice")
if st.button("Analyse my subscriptions"):
    to_analyse = [{"service": s["service"], "monthly_price": s["price"], "status": s["status"]}
                  for s in subs if s["status"] in ("ACTIVE", "APPROVED")]
    if not to_analyse:
        st.info("Activate at least one subscription first.")
    else:
        with st.spinner("Claude is reviewing your subscriptions..."):
            try:
                advice = ai.get_advice(to_analyse)
                st.write(advice["summary"])
                for sug in advice["suggestions"]:
                    st.success(f"**{sug['service']} → {sug['alternative']}**: "
                               f"save about ${sug['monthly_saving']:.2f}/month. {sug['reason']}")
            except Exception as e:
                st.error(f"AI advice failed: {e}")
                # ---------- Live webhook events ----------
st.divider()
st.subheader("📡 Live PayPal webhook events")


@st.fragment(run_every=5)
def live_events():
    events = db.list_events(15)
    latest = events[0]["id"] if events else 0

    # When a new event arrives, refresh the whole dashboard so statuses update
    if "last_event_id" not in st.session_state:
        st.session_state.last_event_id = latest
    elif latest > st.session_state.last_event_id:
        st.session_state.last_event_id = latest
        st.rerun()

    names = {s["sub_id"]: s["service"] for s in db.list_subscriptions()}
    if not events:
        st.info("No events yet. Pause or cancel a subscription and watch this space.")
    else:
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Received (UTC)": e["received_at"],
                        "Event": e["event_type"],
                        "Service": names.get(e["sub_id"], "-"),
                        "Detail": e["detail"],
                    }
                    for e in events
                ]
            )
        )


live_events()
# ---------- AI financial assistant ----------
st.divider()
st.subheader("💬 Ask Bouncer, your AI financial assistant")
st.caption("General guidance on sandbox demo data, not regulated financial advice. "
           "Bouncer can only propose changes: nothing happens until you approve.")

if "api_history" not in st.session_state:
    st.session_state.api_history = []
    st.session_state.chat_display = []
    st.session_state.proposals = []

prompt = st.chat_input("e.g. What should I cancel to save the most money?")
if prompt:
    st.session_state.chat_display.append(("user", prompt))
    st.session_state.api_history.append({"role": "user", "content": prompt})
    with st.spinner("Bouncer is thinking..."):
        try:
            reply = assistant.chat(st.session_state.api_history, st.session_state.proposals)
        except Exception as e:
            reply = f"Sorry, something went wrong: {e}"
    st.session_state.chat_display.append(("assistant", reply))

for role, text in st.session_state.chat_display:
    with st.chat_message(role):
        st.write(text)

for p in list(st.session_state.proposals):
    st.warning(f"Bouncer proposes to **{p['action']} {p['service']}**: {p['reason']}")
    a, b = st.columns(2)
    if a.button("✅ Approve", key=f"approve_{p['id']}"):
        try:
            if p["action"] == "pause":
                paypal_api.suspend_subscription(p["sub_id"])
                db.update_subscription(p["sub_id"], "SUSPENDED", None)
            else:
                paypal_api.cancel_subscription(p["sub_id"])
                db.update_subscription(p["sub_id"], "CANCELLED", None)
            st.session_state.proposals.remove(p)
            st.rerun()
        except Exception as e:
            st.error(f"Could not complete that: {e}")
    if b.button("✖ Dismiss", key=f"dismiss_{p['id']}"):
        st.session_state.proposals.remove(p)
        st.rerun()