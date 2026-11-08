
import json
import uuid
from datetime import datetime, timezone

import anthropic
from dotenv import load_dotenv

import db
import ai_budget
import insights

load_dotenv()
client = anthropic.Anthropic()
MODEL = "claude-sonnet-5-5"  # same model name as ai.py

SYSTEM = """You are Bouncer, a friendly assistant that helps people manage their PayPal subscriptions.
Use the tools to get facts about the user's subscriptions. Never guess prices, dates or statuses.
You cannot pause or cancel anything yourself: use propose_action, which shows the user an Approve button.
Give practical, concise guidance and explain your reasoning briefly.
This is demo data in a PayPal sandbox. You are not a licensed financial adviser, so include a one-line
reminder that this is general guidance whenever you recommend cancelling or spending changes."""

TOOLS = [
    {
        "name": "list_subscriptions",
        "description": "List the user's current (non-cancelled) subscriptions with price, status and days until next charge.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "annual_cost",
        "description": "Calculate the yearly cost of the user's active subscriptions, per service and in total.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "propose_action",
        "description": "Propose pausing or cancelling a subscription. Nothing happens until the user clicks Approve.",
        "input_schema": {
            "type": "object",
            "properties": {
                "sub_id": {"type": "string", "description": "The sub_id from list_subscriptions"},
                "action": {"type": "string", "enum": ["pause", "cancel"]},
                "reason": {"type": "string", "description": "One short sentence for the user"},
            },
            "required": ["sub_id", "action", "reason"],
        },
    },
]


def _days_until(ts):
    if not ts:
        return None
    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    return (dt - datetime.now(timezone.utc)).days


def run_tool(name, args, proposals):
    subs = db.list_subscriptions()

    if name == "list_subscriptions":
        return [
            {
                "sub_id": s["sub_id"],
                "service": s["service"],
                "monthly_price_usd": s["price"],
                "status": s["status"],
                "days_until_next_charge": _days_until(s["next_billing_time"]),
            }
            for s in subs
            if s["status"] != "CANCELLED"
        ]

    if name == "annual_cost":
        live = [s for s in subs if s["status"] in ("ACTIVE", "APPROVED")]
        return {
            "per_service": [
                {"service": s["service"], "yearly_usd": round(s["price"] * 12, 2)} for s in live
            ],
            "total_yearly_usd": round(sum(s["price"] * 12 for s in live), 2),
        }

    if name == "propose_action":
        sub = next((s for s in subs if s["sub_id"] == args.get("sub_id")), None)
        if not sub or sub["status"] == "CANCELLED":
            return {"error": "No such active subscription."}
        if args["action"] == "pause" and sub["status"] != "ACTIVE":
            return {"error": "Only ACTIVE subscriptions can be paused."}
        proposals.append(
            {
                "id": uuid.uuid4().hex[:8],
                "sub_id": sub["sub_id"],
                "service": sub["service"],
                "action": args["action"],
                "reason": args.get("reason", ""),
            }
        )
        return {"status": "proposal shown to the user, awaiting their approval"}

    if name == "budget_status":
        budget = float(db.get_setting("budget", "50"))
        spend = sum(s["price"] for s in subs if s["status"] in ("ACTIVE", "APPROVED"))
        return {
            "monthly_budget_usd": budget,
            "monthly_spend_once_trials_end_usd": round(spend, 2),
            "percent_of_budget_used": round(spend / budget * 100, 1) if budget else None,
            "over_budget": spend > budget,
        }

    if name == "upcoming_charges":
        today = datetime.now(timezone.utc).date()
        days = int(args.get("days", 30))
        return [
            {"date": c["date"].isoformat(), "service": c["service"], "price_usd": c["price"]}
            for c in insights.upcoming_charges(subs, months=3)
            if 0 <= (c["date"] - today).days <= days
        ]

    if name == "recent_events":
        names = {s["sub_id"]: s["service"] for s in subs}
        return [
            {"received_at": e["received_at"], "type": e["event_type"],
             "service": names.get(e["sub_id"]), "detail": e["detail"]}
            for e in db.list_events(10)
        ]

    return {"error": f"Unknown tool {name}"}


# ======================= Proactive watchdog =======================
WATCH_SYSTEM = """You are Bouncer's watchdog. Something just happened on the user's PayPal account and you
decide, on your own, whether the user needs to hear about it right now.
Speak up only when it matters for their money: a free trial about to start charging, a price rise,
a charge that pushes them over budget, a failed payment, a new subscription that duplicates one they
already have, or a shared pool member losing access. Stay quiet for routine or user-initiated changes.
Always check the facts with your tools first. Never guess prices, dates or statuses.
To speak up, call notify_user once. Use concrete numbers, ideally the yearly impact.
Only recommend pause or cancel when it is clearly in the user's interest. They must approve it, so
nothing happens on its own. Otherwise call stay_quiet.
This is demo data in a PayPal sandbox, and you give general guidance, not regulated financial advice."""

DATA_TOOLS = [t for t in TOOLS if t["name"] != "propose_action"] + [
    {
        "name": "budget_status",
        "description": "The user's monthly budget and how much of it their active subscriptions use.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "upcoming_charges",
        "description": "Charges coming up in the next N days (default 30), by date and service.",
        "input_schema": {"type": "object", "properties": {"days": {"type": "integer"}}},
    },
    {
        "name": "recent_events",
        "description": "The 10 most recent events on the account (webhooks, alerts, price changes).",
        "input_schema": {"type": "object", "properties": {}},
    },
]

WATCH_TOOLS = DATA_TOOLS + [
    {
        "name": "notify_user",
        "description": "Alert the user about this event. Optionally recommend pausing or cancelling one "
                       "subscription; the user sees an Approve button and nothing happens without it.",
        "input_schema": {
            "type": "object",
            "properties": {
                "headline": {"type": "string", "description": "At most 8 words"},
                "message": {"type": "string", "description": "1-2 sentences with concrete numbers"},
                "sub_id": {"type": "string", "description": "Only with action: a sub_id from list_subscriptions"},
                "action": {"type": "string", "enum": ["pause", "cancel"]},
                "reason": {"type": "string", "description": "Only with action: one short sentence"},
            },
            "required": ["headline", "message"],
        },
    },
    {
        "name": "stay_quiet",
        "description": "Decide this event doesn't need the user's attention.",
        "input_schema": {
            "type": "object",
            "properties": {"why": {"type": "string"}},
            "required": ["why"],
        },
    },
]


def _checked_action(args):
    """Keep a recommended action only if it is valid for that subscription right now."""
    action, sub_id = args.get("action"), args.get("sub_id")
    if action not in ("pause", "cancel") or not sub_id:
        return None, None
    sub = next((s for s in db.list_subscriptions() if s["sub_id"] == sub_id), None)
    if not sub or sub["status"] == "CANCELLED":
        return None, None
    if action == "pause" and sub["status"] != "ACTIVE":
        return None, None
    return sub_id, action


def review_event(event, service=None):
    """Let the AI decide whether an event deserves an alert.
    Returns None to stay quiet, or a dict with headline, message and an optional sub_id/action/reason."""
    history = [{
        "role": "user",
        "content": "New event on the account:\n" + json.dumps({
            "type": event["event_type"],
            "detail": event["detail"],
            "service": service,
            "sub_id": event["sub_id"],
            "received_at": event["received_at"],
        }, indent=2),
    }]
    for _ in range(5):
        if not ai_budget.allow_call():
            raise RuntimeError("Daily AI limit reached")
        resp = client.messages.create(
            model=MODEL,
            max_tokens=1000,
            system=WATCH_SYSTEM,
            tools=WATCH_TOOLS,
            messages=history,
        )
        if resp.stop_reason != "tool_use":
            return None  # answered in plain text: treat as nothing to report
        history.append({"role": "assistant", "content": resp.content})
        results = []
        for block in resp.content:
            if block.type != "tool_use":
                continue
            if block.name == "stay_quiet":
                return None
            if block.name == "notify_user":
                sub_id, action = _checked_action(block.input)
                clean = lambda v: str(v).strip().strip('"').strip()
                return {
                    "headline": clean(block.input.get("headline", "Bouncer noticed something"))[:80],
                    "message": clean(block.input.get("message", ""))[:600],
                    "sub_id": sub_id or event["sub_id"],
                    "action": action,
                    "reason": block.input.get("reason") if action else None,
                }
            out = run_tool(block.name, block.input, [])
            results.append({"type": "tool_result", "tool_use_id": block.id, "content": json.dumps(out)})
        history.append({"role": "user", "content": results})
    return None


def chat(history, proposals):
    """history: the API message list (already ends with the user's message)."""
    start = len(history)
    try:
        for _ in range(6):
            if not ai_budget.allow_call():
                  raise RuntimeError("Daily AI limit reached. Please try again tomorrow.")
            resp = client.messages.create(
                model=MODEL,
                max_tokens=1500,
                system=SYSTEM,
                tools=TOOLS,
                messages=history,
            )
            history.append({"role": "assistant", "content": resp.content})
            if resp.stop_reason != "tool_use":
                return "".join(b.text for b in resp.content if b.type == "text").strip()

            results = []
            for block in resp.content:
                if block.type == "tool_use":
                    out = run_tool(block.name, block.input, proposals)
                    results.append(
                        {"type": "tool_result", "tool_use_id": block.id, "content": json.dumps(out)}
                    )
            history.append({"role": "user", "content": results})
        return "Sorry, I got stuck. Please try asking again."
    except Exception:
        del history[start:]  # don't leave a half-finished tool turn behind
        raise