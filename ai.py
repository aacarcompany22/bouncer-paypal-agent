
import json
import anthropic
from dotenv import load_dotenv

load_dotenv()  # load .env before the client is created
client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from .env via the environment
MODEL = "claude-sonnet-5-5"  # same model name your smoke test used

# Seeded catalog of fake alternatives (this is demo data, not live prices)
CATALOG = [
    {"name": "ViewLite", "category": "video streaming", "price": 5.99, "note": "ad-supported tier"},
    {"name": "StreamFlix Annual", "category": "video streaming", "price": 8.25, "note": "billed yearly, saves about 17%"},
    {"name": "NoteLite", "category": "notes", "price": 0.00, "note": "free tier, limited storage"},
    {"name": "CloudNotes Annual", "category": "notes", "price": 3.99, "note": "billed yearly"},
    {"name": "GymGo", "category": "fitness", "price": 12.99, "note": "fewer classes, same app"},
    {"name": "FitPass Student", "category": "fitness", "price": 9.99, "note": "student discount"},
    {"name": "OpenTunes", "category": "music", "price": 0.00, "note": "free with ads"},
    {"name": "TuneBox Family", "category": "music", "price": 6.99, "note": "per person, family plan"},
    {"name": "SketchFree", "category": "design", "price": 0.00, "note": "free tier for basic work"},
    {"name": "PixelPro Annual", "category": "design", "price": 11.99, "note": "billed yearly"},
]

SYSTEM = """You are Bouncer, a friendly subscription-saving assistant.
You receive the user's subscriptions and a catalog of alternatives.
Respond with ONLY valid JSON, with no markdown and no extra text, in this shape:
{"summary": "2-3 plain-English sentences about their spending",
 "suggestions": [{"service": "name", "alternative": "name from catalog",
                  "monthly_saving": 0.0, "reason": "one short sentence"}]}
Only suggest alternatives from the catalog. Only suggest ones that save money.
If there is nothing worth suggesting, return an empty suggestions list."""


def get_advice(subscriptions):
    user_msg = (
        "Subscriptions:\n"
        + json.dumps(subscriptions, indent=2)
        + "\n\nCatalog:\n"
        + json.dumps(CATALOG, indent=2)
    )
    msg = client.messages.create(
        model=MODEL,
        max_tokens=800,
        system=SYSTEM,
        messages=[{"role": "user", "content": user_msg}],
    )
    # The reply can contain several blocks (e.g. thinking + text), so keep only the text ones
    text = "".join(block.text for block in msg.content if block.type == "text").strip()
    text = text.replace("```json", "").replace("```", "").strip()

    # If the model added stray text around the JSON, keep only the {...} part
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end != -1:
        text = text[start : end + 1]

    return json.loads(text)