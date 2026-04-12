import os
import requests

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = os.getenv("DISCORD_CHANNEL_ID")
GIST_TOKEN = os.getenv("GIST_TOKEN")
GIST_ID = os.getenv("GIST_ID")


def create_invite():
    url = f"https://discord.com/api/v10/channels/{CHANNEL_ID}/invites"

    response = requests.post(
        url,
        headers={
            "Authorization": f"Bot {DISCORD_TOKEN}",
            "User-Agent": "UTS-Korean-IT-Bot/1.0",
            "Content-Type": "application/json"
        },
        json={
            "max_age": 604800,   # 7 days
            "max_uses": 100
        },
        timeout=20
    )

    print("Discord response:", response.status_code, response.text)
    response.raise_for_status()

    code = response.json()["code"]
    return f"https://discord.gg/{code}"


def update_gist(invite_link):
    gist_url = f"https://api.github.com/gists/{GIST_ID}"

    payload = {
        "files": {
            "latest_invite.txt": {
                "content": invite_link
            }
        }
    }

    response = requests.patch(
        gist_url,
        headers={
            "Authorization": f"token {GIST_TOKEN}",
            "Accept": "application/vnd.github+json"
        },
        json=payload,
        timeout=20
    )

    print("Gist response:", response.status_code, response.text)
    response.raise_for_status()


if __name__ == "__main__":
    invite_link = create_invite()
    update_gist(invite_link)
    print("Latest invite updated:", invite_link)