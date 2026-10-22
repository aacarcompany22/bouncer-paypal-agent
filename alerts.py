
import os

import requests
from dotenv import load_dotenv

load_dotenv()


def send_alert(message):
    url = os.getenv("DISCORD_WEBHOOK_URL")
    if not url:
        print("No DISCORD_WEBHOOK_URL set; alert skipped:", message)
        return
    try:
        requests.post(url, json={"content": message}, timeout=10)
    except Exception as e:
        print("Alert failed:", e)