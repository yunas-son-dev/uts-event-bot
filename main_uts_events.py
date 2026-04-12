# main_uts_events.py
import os
import asyncio
import discord
from dotenv import load_dotenv
from utils.dedupe import load_sent, save_sent
from utils.notify import notify
from bots.uts_events import scrape_uts_events_week_next 

load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("UTS_EVENTS_CHANNEL_ID"))

intents = discord.Intents.default()
client = discord.Client(intents=intents)

HEADER = "**🎉 Upcoming UTS Events This Week!**\n\n"
SENT_FILE = "sent/sent_events.json"

def chunk_messages(header: str, items):
    chunks, cur = [], header
    for date, title, desc, link in items:
        block = f"📅 {date} | 📌 {title}\n🔗 <{link}>\n"
        if desc:
            block += f"📝 {desc}\n"
        block += "\n"
        if len(cur) + len(block) > 2000:
            chunks.append(cur)
            cur = block
        else:
            cur += block
    if cur.strip():
        chunks.append(cur)
    return chunks

@client.event
async def on_ready():
    try:
        print(f"✅ Logged in as {client.user}")

        channel = client.get_channel(CHANNEL_ID)
        if channel is None:
            raise RuntimeError("Channel not found or insufficient permissions.")

        items = await scrape_uts_events_week_next()
        items = [e for e in items if "-" not in e[0]]  # single-day only

        sent = load_sent(SENT_FILE)
        fresh, new_keys = [], []
        for date, title, desc, link in items:
            key = link or f"{date}|{title}"
            if key not in sent:
                fresh.append((date, title, desc, link))
                new_keys.append(key)

        if not fresh:
            await channel.send(HEADER + "😌 No new items.")
            notify("✅ uts_events: sent 0 items.")
        else:
            for part in chunk_messages(HEADER, fresh):
                await channel.send(part)
            notify(f"✅ uts_events: sent {len(fresh)} items.")
            for k in new_keys:
                sent.add(k)
            save_sent(sent, SENT_FILE)

    except Exception as e:
        notify(f"❌ uts_events failed: {e}")
        raise
    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(client.start(DISCORD_TOKEN))
