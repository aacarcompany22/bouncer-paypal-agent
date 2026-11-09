
import math
import os
import time

import requests
from dotenv import load_dotenv

load_dotenv()


def send_alert(message):
    """Post to Discord. Returns (True, None) if Discord accepted it, else (False, reason)."""
    url = (os.getenv("DISCORD_WEBHOOK_URL") or "").strip().strip('"').strip("'")
    if not url:
        print("No DISCORD_WEBHOOK_URL set; alert skipped:", message)
        return False, "DISCORD_WEBHOOK_URL isn't set on this server"
    for attempt in range(2):
        try:
            # Discord rejects messages over 2000 characters
            r = requests.post(url, json={"content": message[:2000]}, timeout=10)
        except Exception as e:
            print("Alert failed:", e)
            return False, f"couldn't reach Discord ({e.__class__.__name__})"
        if r.status_code != 429:
            break
        wait = _retry_after(r)
        if attempt == 0 and wait is not None and wait <= 5:
            time.sleep(wait + 0.2)  # a normal short rate limit: wait and try once more
            continue
        break

    if r.status_code < 300:
        return True, None
    print("Alert rejected by Discord:", r.status_code, r.headers.get("content-type"), r.text[:300])
    if r.status_code in (401, 404):
        return False, f"Discord says the webhook URL is invalid or deleted ({r.status_code})"
    if r.status_code == 429:
        wait = _retry_after(r)
        if wait is None:
            # an HTML page instead of JSON: Discord's network protection has blocked this
            # server's IP address. Common on shared hosts like Render; it usually lifts by itself
            return False, ("Discord has temporarily blocked this server's network address "
                           "(common on shared hosting). It usually lifts within an hour")
        return False, f"Discord is rate-limiting this webhook, try again in {max(1, math.ceil(wait))} seconds"
    return False, f"Discord rejected the message ({r.status_code})"


def _retry_after(r):
    """Seconds Discord asked us to wait, or None if the reply isn't Discord's JSON rate limit."""
    try:
        return float(r.json()["retry_after"])
    except Exception:
        return None