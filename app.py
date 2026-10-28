
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
import alerts
import insights
from dateutil.relativedelta import relativedelta
import search_store
import pools

st.set_page_config(page_title="Bouncer",  layout="wide")
db.init_db()
pools.init()
with open("style.css") as css_file:
    st.markdown(f"<style>{css_file.read()}</style>", unsafe_allow_html=True)
    st.markdown("<style>@import url('https://fonts.googleapis.com/css2?family=Press+Start+2P&display=swap');</style>",
            unsafe_allow_html=True)

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


def go(page):
    st.session_state.page = page


# ---------- Sidebar (unchanged) ----------
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

    st.divider()
    st.header("Alerts")
    current = int(db.get_setting("alert_days", "3"))
    chosen = st.slider("Warn me this many days before a charge", 1, 7, current)
    if chosen != current:
        db.set_setting("alert_days", chosen)
        st.toast(f"Saved: you'll be warned {chosen} day(s) ahead")
    if st.button("Send test alert"):
        alerts.send_alert("Bouncer test alert. Your phone is connected!")
        st.toast("Test alert sent to Discord")

    st.divider()
    st.caption("Monthly budget")
    saved_budget = float(db.get_setting("budget", "50"))
    budget = float(st.slider("Monthly budget (USD)", 10, 500,
                             int(min(max(saved_budget, 10), 500)), step=5,
                             label_visibility="collapsed", key="budget_slider"))
    components.html(ui.sliding_number_html(budget, st.session_state.get("budget_prev", 0)),
                    height=70)
    if st.session_state.get("page", "home") == "home":
        st.markdown(ui.kill_trash_html(), unsafe_allow_html=True)
    st.session_state.budget_prev = budget
    if abs(budget - saved_budget) > 0.001:
        db.set_setting("budget", budget)

subs = db.list_subscriptions()
active = [s for s in subs if s["status"] == "ACTIVE"]


# ---------- Live events (also keeps the page auto-refreshing on new webhooks) ----------
@st.fragment(run_every=5)
def live_events(show_table=True):
    events = db.list_events(15)
    latest = events[0]["id"] if events else 0
    if "last_event_id" not in st.session_state:
        st.session_state.last_event_id = latest
    elif latest > st.session_state.last_event_id:
        st.session_state.last_event_id = latest
        st.rerun()
    if not show_table:
        return
    names = {s["sub_id"]: s["service"] for s in db.list_subscriptions()}
    if not events:
        st.info("No events yet. Pause or cancel a subscription and watch this space.")
    else:
        st.dataframe(pd.DataFrame([{
            "Received (UTC)": e["received_at"],
            "Event": e["event_type"],
            "Service": names.get(e["sub_id"], "-"),
            "Detail": e["detail"],
        } for e in events]))
def days_or_minus_one(s):
    d = days_until(s["next_billing_time"])
    return d if d is not None else -1

def render_ledger_actions():
    sub_id = st.session_state.get("ledger_pick")
    sub = next((s for s in subs if s["sub_id"] == sub_id), None)
    if not sub:
        st.caption("Tick a row in the ledger to act on it.")
        return
    with st.container(key="ledger_actions"):
        st.markdown(f"**Selected:** {sub['service']} &middot; ${sub['price']:.2f}/month "
                    f"&middot; {sub['status'].replace('_', ' ')}")
        if sub["status"] not in ("ACTIVE", "SUSPENDED"):
            st.caption("This subscription can't be changed right now.")
        c1, c2, c3 = st.columns([1, 1, 1])
        if sub["status"] == "ACTIVE" and c1.button("Pause", key="ledger_pause"):
            try:
                paypal_api.suspend_subscription(sub_id)
                db.update_subscription(sub_id, "SUSPENDED", None)
                st.rerun()
            except Exception as e:
                st.error(f"Pause failed: {e}")
        if sub["status"] == "SUSPENDED" and c1.button("Resume", key="ledger_resume"):
            try:
                paypal_api.activate_subscription(sub_id)
                refresh_all()
                st.rerun()
            except Exception as e:
                st.error(f"Resume failed: {e}")
        if sub["status"] in ("ACTIVE", "SUSPENDED") and c2.button("Kill Switch", key="cancel_ledger"):
            request_kill(sub_id)
            st.rerun()
        if c3.button("Clear selection", key="ledger_clear"):
            st.session_state.pop("ledger_pick", None)
            st.rerun()
# ======================= SECTION PAGES =======================
def sec_subscriptions():
    for s in subs:
        c1, c2, c3, c4, c5 = st.columns([2, 1.3, 1.6, 2, 3])
        c1.write(f"**{s['service']}**")
        c2.write(f"${s['price']:.2f}/month")
        c3.markdown(f"<span class='pill {s['status']}'>{s['status'].replace('_', ' ')}</span>",
                 unsafe_allow_html=True)
        d = days_until(s["next_billing_time"])
        c4.write(f"Next charge in {d} day(s)" if d is not None else "No charge yet")

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
            if b2.button("Kill Switch", key=f"cancel_{s['sub_id']}"):
                request_kill(s["sub_id"])
                st.rerun()

    st.divider()
    st.subheader("Subscription ledger")
    st.caption("Click a column header to sort, or use the filter menu on a column.")
    if subs:
        limit = int(db.get_setting("alert_days", "3"))
        ledger = pd.DataFrame([{
            "Service": s["service"],
            "Status": s["status"],
            "Monthly": s["price"],
            "Yearly": round(s["price"] * 12, 2),
            "Budget share": 0 if s["status"] == "CANCELLED" else round(s["price"] / budget * 100, 1),
            "Days left": days_or_minus_one(s),
            "Subscription ID": s["sub_id"],
        } for s in subs])
        picked_rows = ui.show_grid(
            ledger, key="ledger_grid", money_cols=["Monthly", "Yearly"], selectable=True,
            renderers={"Status": ui.STATUS_PILL, "Budget share": ui.BUDGET_BAR,
                       "Days left": ui.days_renderer(limit)},
            row_style=ui.due_row_style(limit), search=True)

        if picked_rows:
            st.session_state.ledger_pick = picked_rows[0].get("Subscription ID")
        render_ledger_actions()
    else:
        st.info("Add a subscription to see the ledger.")

    st.divider()
    st.subheader("Payment history from PayPal")
    if subs:
        labels = {f"{s['service']} ({s['sub_id']})": s["sub_id"] for s in subs}
        choice = st.selectbox("Subscription", list(labels.keys()))
        if st.button("Load payment history"):
            try:
                txs = paypal_api.list_transactions(labels[choice])
                if not txs:
                    st.info("No charges yet. That's expected during the free trial.")
                else:
                    ui.show_grid(pd.DataFrame([{
                        "Time": t.get("time"),
                        "Status": t.get("status"),
                        "Amount": t.get("amount_with_breakdown", {}).get("gross_amount", {}).get("value"),
                    } for t in txs]), key="history_grid", height=300)
            except Exception as e:
                st.error(f"Could not load history: {e}")


def sec_calendar():
    st.subheader("Billing calendar")
    charges = insights.upcoming_charges(subs)
    if not charges:
        st.info("Activate a subscription to see its upcoming charges here.")
        return
    this_month = datetime.now(timezone.utc).date().replace(day=1)
    options = [this_month + relativedelta(months=i) for i in range(12)]
    picked = st.selectbox("Month", options, format_func=lambda d: d.strftime("%B %Y"))
    components.html(insights.calendar_html(charges, picked.year, picked.month),
                    height=620, scrolling=True)

    st.divider()
    st.subheader("Annualised cost overview")
    services = sorted({c["service"] for c in charges})
    drop = st.multiselect("What if I cancelled...", services)
    fig, total = insights.annual_figure(charges, excluded=drop)
    base_total = insights.annual_figure(charges)[1]
    m1, m2 = st.columns(2)
    m1.metric("Projected 12-month spend", f"${total:.2f}")
    m2.metric("Saved by cancelling your selection", f"${base_total - total:.2f}")
    st.plotly_chart(fig, use_container_width=True)


def sec_ai():
    st.subheader("Bouncer AI advice")
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

    st.divider()
    st.subheader("Ask Bouncer, your AI financial assistant")
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
        if a.button("Approve", key=f"approve_{p['id']}"):
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


def sec_audit():
    st.subheader("Audit log search")
    if search_store.enabled():
        st.caption("Powered by Elastic: every PayPal webhook and Bouncer event is indexed and searchable.")
    else:
        st.caption("Elastic isn't configured, so this uses simple local search. "
                   "Add ELASTIC_URL and ELASTIC_API_KEY to .env to switch Elastic on.")

    all_events = db.list_events(500)
    type_options = ["All"] + sorted({e["event_type"] for e in all_events})
    sq1, sq2 = st.columns([3, 1])
    query_text = sq1.text_input("Search events", placeholder="e.g. price change, suspended, StreamFlix",
                                key="audit_search")
    type_filter = sq2.selectbox("Event type", type_options)

    names_by_id = {s["sub_id"]: s["service"] for s in subs}
    rows = []
    try:
        if search_store.enabled():
            rows = search_store.search_events(query_text, None if type_filter == "All" else type_filter)
        else:
            needle = query_text.lower().strip()
            for e in all_events:
                service = names_by_id.get(e["sub_id"], "")
                haystack = f"{e['detail']} {e['event_type']} {service}".lower()
                if needle and needle not in haystack:
                    continue
                if type_filter != "All" and e["event_type"] != type_filter:
                    continue
                rows.append({"received_at": e["received_at"], "event_type": e["event_type"],
                             "service": service, "detail": e["detail"]})
    except Exception as e:
        st.error(f"Search failed: {e}")

    if rows:
        audit_df = pd.DataFrame(rows).reindex(columns=["received_at", "event_type", "service", "detail"])
        audit_df.columns = ["Received (UTC)", "Event", "Service", "Detail"]
        ui.show_grid(audit_df, key="audit_grid", height=360)
    else:
        st.info("No matching events yet. Pause, resume or cancel a subscription, or change a price.")

    if search_store.enabled():
        try:
            counts = search_store.event_counts()
            if counts:
                st.caption("Events by type (an Elastic aggregation)")
                st.bar_chart(pd.Series(counts))
        except Exception as e:
            st.warning(f"Could not load counts: {e}")
        if st.button("Sync existing events to Elastic"):
            try:
                n = search_store.backfill(db.list_events(10000), names_by_id)
                st.success(f"Indexed {n} events.")
            except Exception as e:
                st.error(f"Sync failed: {e}")

    st.divider()
    st.subheader(" Live PayPal webhook events")
    live_events()


def sec_price():
    st.subheader("Price watch")
    st.caption("Merchant demo controls: simulate a service raising its price through PayPal's API. "
               "Bouncer then warns you about the yearly impact.")
    pw1, pw2, pw3 = st.columns([2, 1, 1])
    pw_service = pw1.selectbox("Service", list(SERVICES.keys()), key="pw_service")
    old_price = float(SERVICES[pw_service]["price"])
    pw_price = pw2.number_input("New monthly price (USD)", min_value=0.5,
                                value=round(old_price + 3, 2), step=0.5, key="pw_price")
    pw3.write("")
    pw3.write("")
    if pw3.button("Apply price change"):
        if abs(pw_price - old_price) < 0.005:
            st.info("That's the same as the current price.")
        else:
            try:
                plan_id = SERVICES[pw_service]["plan_id"]
                paypal_api.update_plan_price(plan_id, pw_price)

                SERVICES[pw_service]["price"] = pw_price
                with open("services.json", "w") as f:
                    json.dump(SERVICES, f, indent=2)
                db.update_price_for_plan(plan_id, pw_price)

                diff = (pw_price - old_price) * 12
                detail = (f"{pw_service} price changed ${old_price:.2f} to ${pw_price:.2f}/month "
                          f"({'+' if diff >= 0 else '-'}${abs(diff):.2f} a year)")
                stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
                db.add_event(f"PRICE-{plan_id}-{stamp}", "BOUNCER.PRICE_CHANGE", None, detail)
                alerts.send_alert(f"Price change! {detail}. Open Bouncer to review your options.")
                st.rerun()
            except Exception as e:
                st.error(f"Could not change the price: {e}")

def sec_pools():
    st.caption("Split a subscription with friends. Bouncer requests each share as a PayPal invoice "
               "and tracks who has paid.")
    candidates = [s for s in subs if s["status"] != "CANCELLED"]
    existing = pools.list_pools()

    with st.expander("Create a pool", expanded=not existing):
        if not candidates:
            st.info("Add a subscription first.")
        else:
            labels = {f"{s['service']} (${s['price']:.2f}/month, {s['sub_id']})": s for s in candidates}
            pick = st.selectbox("Subscription to share", list(labels.keys()), key="pool_sub")
            pool_name = st.text_input("Pool name", value="Family plan", key="pool_name")
            people_text = st.text_area(
                "Members, one per line as: Name, email",
                placeholder="Sam, sb-xxxx@personal.example.com",
                key="pool_people",
            )
            due_days = st.number_input("Shares due in (days)", min_value=1, max_value=30, value=3,
                                       key="pool_days")
            if st.button("Create pool and request shares", key="pool_create"):
                people = []
                for line in people_text.splitlines():
                    parts = [p.strip() for p in line.split(",")]
                    if len(parts) >= 2 and "@" in parts[1]:
                        people.append((parts[0], parts[1]))
                if not people:
                    st.error("Add at least one member as: Name, email")
                else:
                    sub = labels[pick]
                    pool_id = pools.create_pool(sub["sub_id"], pool_name, sub["price"],
                                                int(due_days), people)
                    for m in pools.list_members(pool_id):
                        try:
                            url = pools.request_payment(m["id"])
                            alerts.send_alert(f"Pool '{pool_name}': {m['name']}, please pay your "
                                              f"${m['share']:.2f} share here: {url}")
                        except Exception as e:
                            st.error(f"Could not request {m['name']}'s share: {e}")
                    st.rerun()

    if not existing:
        st.info("No pools yet.")

    for pool in existing:
        members = pools.list_members(pool["id"])
        paid = [m for m in members if m["status"] == "PAID"]
        with st.container(border=True):
         h1, h2, h3 = st.columns([3, 1.2, 1.7])
        h1.markdown(f"**{pool['name']}** &middot; ${pool['total']:.2f}/month &middot; "
                        f"shares due {pool['due_date']}")
        if h2.button("Refresh payments", key=f"psync_{pool['id']}"):
            try:
                pools.sync_pool(pool["id"])
            except Exception as e:
                    st.error(f"Could not refresh: {e}")
            st.rerun()
        if h3.button("Demo: pass the deadline", key=f"pdemo_{pool['id']}"):
                pools.expire_pool(pool["id"])
                for msg in pools.enforce_deadlines():
                    alerts.send_alert(f"Access revoked: {msg}")
                st.rerun()
        collected = sum(m["share"] for m in paid)
        st.progress(len(paid) / len(members) if members else 0,
                        text=f"{len(paid)} of {len(members)} shares paid "
                             f"(${collected:.2f} collected)")
        status_class = {"PAID": "ACTIVE", "UNPAID": "APPROVAL_PENDING",
                            "NOT_REQUESTED": "APPROVAL_PENDING", "CANCELLED": "CANCELLED"}
        access_class = {"ACTIVE": "ACTIVE", "PENDING": "APPROVAL_PENDING", "REVOKED": "REVOKED"}
        for m in members:
                c1, c2, c3, c4, c5 = st.columns([2, 1, 1.5, 1.5, 2])
                c1.markdown(f"**{m['name']}**")
                c1.caption(m["email"])
                c2.write(f"${m['share']:.2f}")
                c3.markdown(f"<span class='pill {status_class.get(m['status'], 'CANCELLED')}'>"
                            f"{m['status'].replace('_', ' ')}</span>", unsafe_allow_html=True)
                c4.markdown(f"<span class='pill {access_class.get(m['access'], 'CANCELLED')}'>"
                            f"ACCESS {m['access']}</span>", unsafe_allow_html=True)
                if m["pay_url"]:
                    c5.link_button("Open pay link", m["pay_url"])
                elif c5.button("Request share", key=f"preq_{m['id']}"):
                    try:
                        pools.request_payment(m["id"])
                        st.rerun()
                    except Exception as e:
                        st.error(f"Could not request: {e}")
                        live_events(False)

SECTIONS = {
    "subs": ("Subscriptions", sec_subscriptions),
    "calendar": ("Calendar and costs", sec_calendar),
    "ai": ("AI assistant and advice", sec_ai),
    "audit": ("Audit log and events", sec_audit),
    "price": ("Price watch", sec_price),
    "pools": ("Shared pools", sec_pools)
}

CARD_TEXT = {
    "subs": ("Subscriptions", "Pause, resume or cancel, plus your ledger and payment history."),
    "calendar": ("Calendar & costs", "Upcoming charges and your 12-month spend."),
    "ai": ("AI assistant", "Ask Bouncer for savings ideas and approve its suggestions."),
    "audit": ("Audit log", "Search every PayPal event, live."),
    "price": ("Price watch", "Simulate a price rise and get alerted."),
    "pools": ("Shared pools", "Split a subscription and collect shares through PayPal."),
}


def _svg(inner):
    return ("<svg viewBox='0 0 56 56' width='58' height='58' fill='none' stroke='#00d632' "
            "stroke-width='2.5' stroke-linecap='round' stroke-linejoin='round'>" + inner + "</svg>")

PALETTE = {
    "k": "#0b0f19", "w": "#ffffff", "s": "#cfd6e8", "S": "#8f9ab8",
    "b": "#4da3ff", "r": "#ff4b4b", "y": "#ffbb00", "Y": "#c98a00",
    "g": ("#00d632", "blink"), "e": ("#4dd0ff", "blink"),
    "a": ("#ff4b4b", "blink"), "x": ("#ffffff", "blink"),
}

SPRITE_SUBS = [
    "................",
    "................",
    "................",
    ".kkkkkkkkkkkkkk.",
    ".kbbbbbbbbbbbbk.",
    ".kkkkkkkkkkkkkk.",
    ".kkkkkkkkkkkkkk.",
    ".kbbbbbbbbbbbbk.",
    ".kbyyybbbbbbbbk.",
    ".kbyyybbbbbbbbk.",
    ".kbbbbbbbwwwwbk.",
    ".kbbbbbbbbbbbbk.",
    ".kkkkkkkkkkkkkk.",
    "................",
    "................",
    "................",
]

SPRITE_CALENDAR = [
    "................",
    "...kk......kk...",
    "...ks......sk...",
    ".kkkkkkkkkkkkkk.",
    ".krrrrrrrrrrrrk.",
    ".krrrrrrrrrrrrk.",
    ".kkkkkkkkkkkkkk.",
    ".kwwwwwwwwwwwwk.",
    ".kwggwSSwSSwwwk.",
    ".kwggwSSwSSwwwk.",
    ".kwwwwwwwwwwwwk.",
    ".kwSSwSSwwwwwwk.",
    ".kwSSwSSwwwwwwk.",
    ".kkkkkkkkkkkkkk.",
    "................",
    "................",
]

SPRITE_ROBOT = [
    ".......aa.......",
    ".......kk.......",
    "..kkkkkkkkkkkk..",
    ".kssssssssssssk.",
    ".kskkkkkkkkkksk.",
    ".kskeekkkkeeksk.",
    ".kskeekkkkeeksk.",
    ".kskkkkkkkkkksk.",
    ".kssssssssssssk.",
    "..kkkkkkkkkkkk..",
    ".....kssssk.....",
    "...kkkkkkkkkk...",
    "..kbbbbbbbbbbk..",
    "..kbbwbbbbwbbk..",
    "..kbbbbbbbbbbk..",
    "...kkkkkkkkkk...",
]

SPRITE_MAGNIFIER = [
    "................",
    "....kkkkkk......",
    "...kbbbbbbk.....",
    "..kbbwwbbbbk....",
    "..kbwwbbbbbk....",
    "..kbbbbbbbbk....",
    "..kbbbbbbbbk....",
    "..kbbbbbbbbk....",
    "...kbbbbbbk.....",
    "....kkkkkkkk....",
    ".........kYYk...",
    "..........kYYk..",
    "...........kYYk.",
    "............kkk.",
    "................",
    "................",
]

SPRITE_COIN = [
    ".............x..",
    "............xxx.",
    ".....kkkkkk..x..",
    "...kkyyyyyykk...",
    "..kyyyyyyyyyyk..",
    ".kyyyyyYYyyyyyk.",
    ".kyyyyYYYYYyyyk.",
    ".kyyyyYyyyyyyyk.",
    ".kyyyyYYYYyyyyk.",
    ".kyyyyyyyyYyyyk.",
    ".kyyyyYYYYYyyyk.",
    ".kyyyyyYYyyyyyk.",
    "..kyyyyyyyyyyk..",
    "...kkyyyyyykk...",
    ".....kkkkkk.....",
    "................",
]
SPRITE_POOL = [
    "................",
    ".....kkkkkk.....",
    ".....kssssk.....",
    ".....kssssk.....",
    "kkkk.kkkkkk.kkkk",
    "kssk.kbbbbk.kssk",
    "kssk.kbbbbk.kssk",
    "kkkk.kbbbbk.kkkk",
    "kbbk.kbbbbk.kbbk",
    "kbbk.kbbbbk.kbbk",
    "kkkk.kbbbbk.kkkk",
    "....kbbbbbbk....",
    "....kbbyybbk....",
    "....kbbbbbbk....",
    "....kkkkkkkk....",
    "................",
]


def _pixels(rows, anim="bob"):
    rects = ""
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch == ".":
                continue
            color = PALETTE[ch]
            cls = ""
            if isinstance(color, tuple):
                color, name = color
                cls = f" class='{name}'"
            rects += f"<rect{cls} x='{x}' y='{y}' width='1.02' height='1.02' fill='{color}'/>"
    return (f"<svg class='pix {anim}' viewBox='0 0 16 16' width='72' height='72' "
            f"shape-rendering='crispEdges'>{rects}</svg>")


ICONS = {
    "subs": _pixels(SPRITE_SUBS),
    "calendar": _pixels(SPRITE_CALENDAR),
    "ai": _pixels(SPRITE_ROBOT),
    "audit": _pixels(SPRITE_MAGNIFIER, "sweep"),
    "price": _pixels(SPRITE_COIN),
    "pools": _pixels(SPRITE_POOL),
}


def card_stat(key):
    if key == "subs":
        live = len([s for s in subs if s["status"] != "CANCELLED"])
        killed = len([s for s in subs if s["status"] == "CANCELLED"])
        return str(live), "subscriptions tracked" + (f", {killed} cancelled" if killed else "")
    if key == "calendar":
        days = [d for d in (days_until(s["next_billing_time"]) for s in active) if d is not None]
        return (str(min(days)), "days to next charge") if days else ("-", "no upcoming charges")
    if key == "ai":
        return "AI", "ask Bouncer anything"
    if key == "audit":
        return str(len(db.list_events(500))), "events logged"
    if key == "pools":
        return str(len(pools.list_pools())), "pools running"
    return str(len(SERVICES)), "plans watched"


def render_cards():
    st.markdown("### Explore")
    layout = [
        [("calendar", 1), ("subs", 1), ("ai", 1)],
        [("audit", 1), ("price", 1), ("pools", 1)],
    ]

    for row in layout:
        cols = st.columns([w for _k, w in row])
        for col, (key, _w) in zip(cols, row):
            if key is None:
                continue
            title, blurb = CARD_TEXT[key]
            big, small = card_stat(key)
            with col:
                with st.container(border=True, key=f"card_{key}"):
                    st.markdown(
                        f"<div class='card-icon'>{ICONS[key]}</div>"
                        f"<div class='card-title'>{title}</div>"
                        f"<div class='card-blurb'>{blurb}</div>"
                        f"<div class='card-stat'><span class='card-big'>{big}</span> "
                        f"<span class='card-small'>{small}</span></div>"
                        f"<div class='card-cta'>Open <span>&rarr;</span></div>",
                        unsafe_allow_html=True,
                    )
                    st.button("Open", key=f"open_{key}", on_click=go, args=(key,))

def request_kill(sub_id):
    st.session_state.kill_target = sub_id
    st.session_state.pop("kill_receipt", None)


def abort_kill():
    st.session_state.pop("kill_target", None)
    st.session_state.map_nonce = st.session_state.get("map_nonce", 0) + 1


def render_kill_panel():
    receipt = st.session_state.get("kill_receipt")
    if receipt:
        with st.container(key="kill_receipt"):
            st.markdown(
                f"<div class='kill-title ok'>KILL SWITCH COMPLETE</div>"
                f"<div><b>{receipt['service']}</b> is now <b>{receipt['status']}</b> at PayPal "
                f"(confirmed {receipt['when']}). You save ${receipt['yearly']:.2f} a year.</div>"
                f"<div class='kill-note'>Cancelling stops future charges. "
                f"Anything already owed is not erased.</div>",
                unsafe_allow_html=True,
            )
            st.button("Dismiss", key="kill_receipt_dismiss",
                      on_click=lambda: st.session_state.pop("kill_receipt", None))

    target = st.session_state.get("kill_target")
    if not target:
        return
    sub = next((s for s in db.list_subscriptions() if s["sub_id"] == target), None)
    if not sub or sub["status"] == "CANCELLED":
        st.session_state.pop("kill_target", None)
        return

    with st.container(key="kill_panel"):
        d = days_until(sub["next_billing_time"])
        nxt = f"Next charge in {d} day(s)." if d is not None else "No charge scheduled yet."
        st.markdown(
            f"<div class='kill-title'>KILL SWITCH ARMED</div>"
            f"<div><b>{sub['service']}</b> &middot; ${sub['price']:.2f}/month &middot; "
            f"{sub['status']} &middot; {nxt}<br>This tells PayPal to cancel the subscription and "
            f"can't be undone. You would save ${sub['price'] * 12:.2f} a year.</div>",
            unsafe_allow_html=True,
        )
        c1, c2, _ = st.columns([2, 1, 3])
        if c1.button("Confirm: cancel with PayPal", key="kill_confirm"):
            try:
                paypal_api.cancel_subscription(target)
                proof = paypal_api.get_subscription(target)  # PayPal's own record of the result
                status = proof.get("status", "CANCELLED")
                db.update_subscription(target, status, None)
                yearly = sub["price"] * 12
                detail = (f"Kill Switch used on {sub['service']}. PayPal reports {status}. "
                          f"Saves ${yearly:.2f} a year.")
                stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
                db.add_event(f"KILL-{target}-{stamp}", "BOUNCER.KILL_SWITCH", target, detail)
                alerts.send_alert(f"Kill Switch: {detail}")
                st.session_state.kill_receipt = {
                    "service": sub["service"], "status": status, "yearly": yearly,
                    "when": proof.get("status_update_time", "just now"),
                }
                st.session_state.pop("kill_target", None)
                st.session_state.map_nonce = st.session_state.get("map_nonce", 0) + 1
                st.rerun()
            except Exception as e:
                st.error(f"Kill Switch failed: {e}")
        c2.button("Abort", key="kill_abort", on_click=abort_kill)
# ======================= HOME =======================
def render_banner():
    def tile(label, value, cap, cls=""):
        return (f"<div class='kpi {cls}'><span class='ar'>&nearr;</span>"
                f"<div class='lab'>{label}</div><div class='num'>{value}</div>"
                f"<div class='cap'>{cap}</div></div>")

    with st.container(key="banner"):
        head_l, head_r = st.columns([4, 1])
        with head_l:
            st.markdown(ui.text_roll_html("Bouncer"), unsafe_allow_html=True)
            st.caption("The bouncer for your PayPal subscriptions. Sandbox mode: no real money moves.")
        with head_r:
            if st.button("Refresh from PayPal"):
                refresh_all()
                st.rerun()

        alert_msg = None
        limit = int(db.get_setting("alert_days", "3"))
        for s in active:
            d = days_until(s["next_billing_time"])
            if d is not None and d <= limit:
                alert_msg = f"Hold up! {s['service']} starts charging ${s['price']:.2f} in {d} day(s)."
                break

        days = [d for d in (days_until(s["next_billing_time"]) for s in active) if d is not None]
        tracked = len([s for s in subs if s["status"] != "CANCELLED"])
        cancelled = len([s for s in subs if s["status"] == "CANCELLED"])
        monthly = sum(s["price"] for s in active)

        top_l, top_r = st.columns([1.65, 1])
        with top_l:
            with st.container(key="tile_guard"):
                if alert_msg:
                    scene = ui.bouncer_html(alert_msg, alert=True)
                elif active:
                    scene = ui.bouncer_html(
                        f"All clear, boss. I'm watching {len(active)} subscription(s).", False)
                else:
                    scene = ui.bouncer_html("Nobody's on the list yet. Add a subscription.", False)
                components.html(scene, height=255)
        with top_r:
            st.markdown(
                "<div class='kpi-grid'>"
                + tile("Active subscriptions", len(active), f"of {tracked} tracked", "hl")
                + tile("Monthly cost", f"${monthly:.2f}", "once trials end")
                + tile("Cancelled", cancelled, "subscriptions ended")
                + tile("Next charge", str(min(days)) if days else "-",
                       "days away" if days else "nothing scheduled")
                + "</div>",
                unsafe_allow_html=True,
            )

        if subs:
            mid_l, mid_r = st.columns([1.5, 1])
            with mid_l:
                with st.container(key="tile_map"):
                    components.html(
                        ui.kill_map_html(subs, budget, st.session_state.get("map_nonce", 0)),
                        height=480)
            with mid_r:
                rings = ui.spend_rings_html(subs, budget)
                rings = (rings.replace("body {", "html, body { height:100%; } body {", 1)
                              .replace(".card {", ".card { display:flex; flex-direction:column; "
                                       "height:100%; box-sizing:border-box;", 1)
                              .replace(".body {", ".body { flex:1;", 1))
                components.html(rings, height=480)

            with st.container(key="killbridge"):
                for s in subs:
                    if s["status"] in ("ACTIVE", "SUSPENDED"):
                        st.button(f"kill-{s['sub_id']}", key=f"bridge_{s['sub_id']}",
                                  on_click=request_kill, args=(s["sub_id"],))

def render_home():
    render_banner()
    render_cards()
    live_events(False)


def render_detail(key):
    title, section = SECTIONS[key]
    blurb = CARD_TEXT[key][1]
    big, small = card_stat(key)
    st.button("← Back to dashboard", key="back", on_click=go, args=("home",))
    st.markdown(
        f"<div class='pg-hero'>"
        f"<div class='pg-icon'>{ICONS[key]}</div>"
        f"<div><div class='pg-kicker'>PLAYER 1 &middot; STAGE</div>"
        f"<div class='pg-title'>{title}</div>"
        f"<div class='pg-sub'>{blurb}</div></div>"
        f"<div class='pg-score'><span>{big}</span><small>{small}</small></div>"
        f"</div>",
        unsafe_allow_html=True,
    )
    with st.container(key=f"panel_{key}"):
        section()
   
   


page = st.session_state.get("page", "home")
render_kill_panel()
if page in SECTIONS:
    render_detail(page)
else:
    render_home()