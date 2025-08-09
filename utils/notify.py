import os
import requests
from dotenv import load_dotenv

load_dotenv()
WEBHOOK_URL = os.getenv("ADMIN_WEBHOOK_URL")  # GitHub Actions Secrets나 .env에 추가

def notify(message: str):
    """Send a notification to the admin webhook"""
    if not WEBHOOK_URL:
        print("⚠️ No ADMIN_WEBHOOK_URL set, skipping notify.")
        return

    try:
        res = requests.post(WEBHOOK_URL, json={"content": message})
        if res.status_code != 204:
            print(f"⚠️ Webhook returned status {res.status_code}: {res.text}")
    except Exception as e:
        print(f"❌ Failed to send webhook notification: {e}")
