import asyncio
import os
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
from playwright.async_api import async_playwright

BASE_URL = "https://www.activateuts.com.au/events/?orderby=featured"
CARDS_SELECTOR = "div.tile.tile--event"
SCRAPE_TIMEOUT = 300


def _sydney_today() -> date:
    return datetime.now(ZoneInfo("Australia/Sydney")).date()


def _next_week_range_sydney() -> tuple[date, date]:
    """Next Monday .. Sunday in Australia/Sydney."""
    today = _sydney_today()
    this_monday = today - timedelta(days=today.weekday())
    next_monday = this_monday + timedelta(days=7)
    next_sunday = next_monday + timedelta(days=6)
    return next_monday, next_sunday


async def _scrape() -> list[tuple[str, str, str, str]]:
    events = []
    start_of_week, end_of_week = _next_week_range_sydney()
    today = _sydney_today()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page_num = 1
        has_more = True

        while has_more:
            url = f"{BASE_URL}&page_num={page_num}"
            page = await browser.new_page()

            try:
                for attempt in range(3):
                    try:
                        await page.goto(url, timeout=60_000)
                        await page.wait_for_selector(CARDS_SELECTOR, timeout=60_000)
                        break
                    except Exception as e:
                        if attempt == 2:
                            raise
                        await asyncio.sleep(2 * (attempt + 1))

                cards = await page.query_selector_all(CARDS_SELECTOR)
                print(f"[uts_events] Page {page_num}: {len(cards)} cards")

                if not cards:
                    has_more = False
                    break

                for card in cards:
                    badge = await card.query_selector("span.tile__badge")
                    if not badge:
                        continue
                    date_str = (await badge.inner_text()).strip()

                    try:
                        parts = date_str.split()
                        y = today.year
                        if "-" in date_str and len(parts) >= 5 and parts[2] == "-":
                            # range: "3 MAR - 28 APR"
                            s_day, s_mon = int(parts[0]), parts[1]
                            e_day, e_mon = int(parts[3]), parts[4]
                            start_date = datetime.strptime(
                                f"{s_day} {s_mon} {y}", "%d %b %Y"
                            ).date()
                            end_date = datetime.strptime(
                                f"{e_day} {e_mon} {y}", "%d %b %Y"
                            ).date()
                        else:
                            # single: "14 APR"
                            d, m = parts[0], parts[1]
                            start_date = end_date = datetime.strptime(
                                f"{d} {m} {y}", "%d %b %Y"
                            ).date()
                    except Exception:
                        continue

                    # skip if doesn't overlap next week
                    if end_date < start_of_week or start_date > end_of_week:
                        continue

                    # skip multi-week events (range longer than 7 days)
                    if (end_date - start_date).days > 7:
                        continue

                    title_el = await card.query_selector("h3.tile__title")
                    link_el = await card.query_selector("a")
                    desc_el = await card.query_selector("p.tile__desc")

                    if not title_el or not link_el:
                        continue

                    title = (await title_el.inner_text()).strip()
                    href = await link_el.get_attribute("href")
                    link = (
                        f"https://www.activateuts.com.au{href}"
                        if href and href.startswith("/")
                        else href or ""
                    )
                    desc = (await desc_el.inner_text()).strip() if desc_el else ""

                    events.append((date_str, title, desc, link))

            finally:
                await page.close()

            has_more = len(cards) >= 15
            if has_more:
                page_num += 1
            await asyncio.sleep(0.6)

        await browser.close()

    return events


async def scrape_uts_events_week_next() -> list[tuple[str, str, str, str]]:
    """Return events overlapping next week (Mon–Sun, Sydney time).

    Each item: (date_str, title, desc, link)
    Raises asyncio.TimeoutError if scrape exceeds 5 minutes.
    """
    return await asyncio.wait_for(_scrape(), timeout=SCRAPE_TIMEOUT)


def format_discord_message(events: list[tuple[str, str, str, str]]) -> list[str]:
    """Split events into <=1900-char Discord messages."""
    if not events:
        return [
            "**🎉 Upcoming UTS Events Next Week!**\n\n"
            "😌 No events found for next week."
        ]

    header = "**🎉 Upcoming UTS Events Next Week!**\n\n"
    chunks: list[str] = []
    cur = header

    for date_str, title, desc, link in events:
        block = f"📅 **{date_str}** | 📌 {title}\n"
        if link:
            block += f"🔗 <{link}>\n"
        if desc:
            snippet = desc[:200] + ("..." if len(desc) > 200 else "")
            block += f"📝 {snippet}\n"
        block += "\n"

        if len(cur) + len(block) > 1900:
            chunks.append(cur)
            cur = header + block
        else:
            cur += block

    if cur.strip():
        chunks.append(cur)
    return chunks


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    async def _test():
        events = await scrape_uts_events_week_next()
        print(f"\n총 {len(events)}개 이벤트")
        for e in events:
            print(f"  {e[0]} | {e[1]}")

    asyncio.run(_test())