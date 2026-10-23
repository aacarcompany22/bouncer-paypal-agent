
import json
import uuid
from datetime import datetime, timezone

import anthropic
from dotenv import load_dotenv

import db

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

    return {"error": f"Unknown tool {name}"}


def chat(history, proposals):
    """history: the API message list (already ends with the user's message)."""
    start = len(history)
    try:
        for _ in range(6):
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