
import os
import requests
from dotenv import load_dotenv
import anthropic

load_dotenv()

# 1. PayPal sandbox token
r = requests.post(
    f"{os.getenv('PAYPAL_BASE_URL')}/v1/oauth2/token",
    auth=(os.getenv("PAYPAL_CLIENT_ID"), os.getenv("PAYPAL_SECRET")),
    data={"grant_type": "client_credentials"},
)
print("PayPal status:", r.status_code)
print("Token starts with:", r.json().get("access_token", "")[:10], "...")

# 2. Claude API
client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from the environment
msg = client.messages.create(
    model="claude-sonnet-5-5",
    max_tokens=50,
    messages=[{"role": "user", "content": "Say hello in five words."}],
)
print("Claude says:", msg.content[0].text)