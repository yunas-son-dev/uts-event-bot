import os
import asyncio
import discord
from dotenv import load_dotenv
from utils.dedupe import load_sent, save_sent
from utils.notify import notify
from bots.prosple import scrape_prosple_it

load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("PROSPLE_CHANNEL_ID"))

intents = discord.Intents.default()
client = discord.Client(intents=intents)

HEADER = "**🚀 New IT Roles (Prosple)**\n\n"
SENT_FILE = "sent/sent_prosple.json"

def chunk_messages(header: str, items):
    chunks, cur = [], header
    # items: (company, role, location, salary, start_date, link)
    for company, role, location, salary, start_date, link in items:
        block = (
            f"🏢 {company} 🔗 [Link]({link})\n"
            f"💼 {role}\n"
            f"📍 {location}" + (f" | 💰 {salary}" if salary else "💰No information") + "\n"
            f"------------------------------------------------------------------------\n\n"
        )
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

        # [(company, role, location, salary, start_date, link)]
        items = await scrape_prosple_it()

        ## de-dup criteria: Link or Company|Roles
        ## sent = load_sent(SENT_FILE)
        ## fresh, new_keys = [], []
        ## for company, role, location, salary, start_date, link in items:
        ##     key = link or f"{company}|{role}"
        ##     if key not in sent:
        ##         fresh.append((company, role, location, salary, start_date, link))
        ##         new_keys.append(key)

        ## TEST mode
        fresh = items
        new_keys = []
        sent = set()

        if not fresh:
            await channel.send(HEADER + "😌 No new items.")
            notify("✅ prosple: sent 0 items.")
        else:
            for part in chunk_messages(HEADER, fresh):
                await channel.send(part)
            notify(f"✅ prosple: sent {len(fresh)} items.")
            ## for k in new_keys:
            ##     sent.add(k)
            ## save_sent(sent, SENT_FILE)
    except Exception as e:
        notify(f"❌ prosple failed: {e}")
        raise
    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(client.start(DISCORD_TOKEN))
