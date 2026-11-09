
import os

import requests
from dotenv import load_dotenv

load_dotenv()


def send_alert(message):
    """Post to Discord. Returns (True, None) if Discord accepted it, else (False, reason)."""
    url = (os.getenv("DISCORD_WEBHOOK_URL") or "").strip().strip('"').strip("'")
    if not url:
        print("No DISCORD_WEBHOOK_URL set; alert skipped:", message)
        return False, "DISCORD_WEBHOOK_URL isn't set on this server"
    try:
        # Discord rejects messages over 2000 characters
        r = requests.post(url, json={"content": message[:2000]}, timeout=10)
    except Exception as e:
        print("Alert failed:", e)
        return False, f"couldn't reach Discord ({e.__class__.__name__})"
    if r.status_code >= 300:
        print("Alert rejected by Discord:", r.status_code, r.text[:200])
        if r.status_code in (401, 404):
            return False, f"Discord says the webhook URL is invalid or deleted ({r.status_code})"
        if r.status_code == 429:
            return False, "Discord is rate-limiting this webhook, try again in a few seconds"
        return False, f"Discord rejected the message ({r.status_code})"
    return True, None