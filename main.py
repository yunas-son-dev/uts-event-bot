import os
import asyncio
import discord
from dotenv import load_dotenv
from playwright.async_api import async_playwright
import datetime
from utils.dedupe import load_sent, save_sent
from utils.notify import notify

# ✅ 1. Load environment variables
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID"))

# ✅ 2. Discord client declaration
intents = discord.Intents.default()
client = discord.Client(intents=intents)

def format_event(date, title, desc, link):
    msg = f"📆 {date} | 📌 {title}\n🔗 <{link}>\n"
    if desc:
        msg += f"📝 {desc}\n"
    msg += "\n"
    return msg

def chunk_messages(events, header="**🎉 Upcoming UTS Events This Week!**\n\n", limit=2000):
    chunks = []
    current = header
    for event in events:
        if len(current) + len(event) > limit:
            chunks.append(current)
            current = event
        else:
            current += event
    if current.strip():
        chunks.append(current)
    return chunks

# ✅ 3. Event scraping function (async)
async def scrape_events():
    print("🕸️ Scraping started")
    BASE_URL = "https://www.activateuts.com.au/events/?orderby=featured"
    events = []
    today = datetime.date.today()
    start_of_week = today - datetime.timedelta(days=today.weekday())
    end_of_week = start_of_week + datetime.timedelta(days=6)
    page_num = 1
    has_more = True

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        while has_more:
            url = f"{BASE_URL}&page_num={page_num}"
            page = await browser.new_page()
            print(f"🌐 Opening page... {url}")
            for attempt in range(3):
                try:
                    await page.goto(url, timeout=60000)
                    await page.wait_for_selector("div.tile.tile--event", timeout=60000)
                    break
                except Exception as e:
                    if attempt == 2:
                        raise
                    await asyncio.sleep(2)
            cards = await page.query_selector_all("div.tile.tile--event")
            print(f"📦 Number of event cards (page {page_num}): {len(cards)}")

            if not cards:
                has_more = False
                await page.close()
                break

            for card in cards:
                date_str = await (await card.query_selector("span.tile__badge")).inner_text()
                try:
                    parts = date_str.strip().split()
                    # Period (e.g. '14 JUL - 31 OCT') or single date (e.g. '5 AUG')
                    if '-' in date_str:
                        # Period event, skip
                        continue
                    elif len(parts) >= 2:
                        try:
                            day = int(parts[0])
                            month = parts[1]
                            year = today.year
                            start_date = end_date = datetime.datetime.strptime(f"{day} {month} {year}", "%d %b %Y").date()
                        except Exception as e:
                            continue
                    else:
                        continue
                except Exception as e:
                    print("❌ Date parsing failed:", date_str, e)
                    continue

                # Only add events within this week
                if end_date < start_of_week or start_date > end_of_week:
                    continue

                title = await (await card.query_selector("h3.tile__title")).inner_text()
                desc = await (await card.query_selector("p.tile__desc")).inner_text()
                href = await (await card.query_selector("a")).get_attribute("href")
                full_link = f"https://www.activateuts.com.au{href}"
                events.append((date_str.strip(), title.strip(), desc.strip(), full_link))

            await page.close()
            # If less than 15 cards, consider it the last page and stop
            if len(cards) < 15:
                has_more = False
            else:
                page_num += 1

        await browser.close()
        print("🧹 Browser closed")
        return events

def dedupe_events(events, sent_keys):
    new_events = []
    for date, title, desc, link in events:
        key = f"{date}|{title}|{link}"
        if key not in sent_keys:
            new_events.append((date, title, desc, link))
            sent_keys.add(key)
    return new_events

# ✅ 4. Discord bot event definition
@client.event
async def on_ready():
    print(f"✅ Logged in as {client.user}")

    channel = client.get_channel(CHANNEL_ID)
    print("📡 Channel object:", channel)

    if channel is None:
        print("❌ Channel not found. Check CHANNEL_ID or permissions!")
        await client.close()
        return

    sent_keys = load_sent()
    new_events = []

    try:
        events = await scrape_events()

        # Only single-day events (exclude periods)
        single_day_events = [e for e in events if '-' not in e[0]]

        # dedupe
        new_events = dedupe_events(single_day_events, sent_keys)

        # Send messages (split by 2,000 chars, link preview OFF)
        if not new_events:
            msg = "**🎉 Upcoming UTS Events This Week!**\n\n😌 No new single-day events this week."
            await channel.send(msg)
            notify("✅ UTS bot sent 0 events this week.")
        else:
            event_blocks = [format_event(date, title, desc, link) for date, title, desc, link in new_events]
            for chunk in chunk_messages(event_blocks):
                await channel.send(chunk)
            notify(f"✅ UTS bot sent {len(new_events)} events this week.")

        # ✅ Only update/save sent_keys after successful send
        save_sent(sent_keys)

    except Exception as e:
        # On failure, only notify via webhook, do not send channel message
        notify(f"❌ UTS event bot failed: {e}")
        raise
    finally:
        await client.close()

# ✅ 5. Run
if __name__ == "__main__":
    asyncio.run(client.start(DISCORD_TOKEN))
