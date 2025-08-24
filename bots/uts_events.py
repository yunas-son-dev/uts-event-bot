import asyncio
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
from playwright.async_api import async_playwright

BASE_URL = "https://www.activateuts.com.au/events/?orderby=featured"
CARDS_SELECTOR = "div.tile.tile--event"


def _sydney_today() -> date:
    return datetime.now(ZoneInfo("Australia/Sydney")).date()


def _next_week_range_sydney() -> tuple[date, date]:
    """Next Monday .. Sunday in Australia/Sydney."""
    today = _sydney_today()
    this_monday = today - timedelta(days=today.weekday())
    next_monday = this_monday + timedelta(days=7)
    next_sunday = next_monday + timedelta(days=6)
    return next_monday, next_sunday


async def scrape_uts_events_week_next():
    """
    Return events overlapping next week (Mon..Sun, Sydney time).
    Each item: (date_str, title, desc, link)
    """
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
                # Retry up to 3 times for loading
                for attempt in range(3):
                    try:
                        await page.goto(url, timeout=60000)
                        await page.wait_for_selector(CARDS_SELECTOR, timeout=60000)
                        break
                    except Exception as e:
                        if attempt == 2:
                            raise
                        await asyncio.sleep(2 * (attempt + 1))

                cards = await page.query_selector_all(CARDS_SELECTOR)
                if not cards:
                    has_more = False
                    break

                for card in cards:
                    badge = await card.query_selector("span.tile__badge")
                    if not badge:
                        continue
                    date_str = (await badge.inner_text()).strip()

                    # Parse single date or range; keep if overlaps this week
                    try:
                        parts = date_str.split()
                        y = today.year
                        if "-" in date_str and len(parts) >= 5 and parts[2] == "-":
                            s_day, s_mon = int(parts[0]), parts[1]
                            e_day, e_mon = int(parts[3]), parts[4]
                            start_date = datetime.strptime(
                                f"{s_day} {s_mon} {y}", "%d %b %Y"
                            ).date()
                            end_date = datetime.strptime(
                                f"{e_day} {e_mon} {y}", "%d %b %Y"
                            ).date()
                        else:
                            d, m = parts[0], parts[1]
                            start_date = end_date = datetime.strptime(
                                f"{d} {m} {y}", "%d %b %Y"
                            ).date()
                    except Exception:
                        continue

                    if end_date < start_of_week or start_date > end_of_week:
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
                        else href
                    )
                    desc = (await desc_el.inner_text()).strip() if desc_el else ""

                    events.append((date_str, title, desc, link))
            finally:
                await page.close()

            # Heuristic: if fewer than 15 cards, likely last page
            has_more = len(cards) >= 15
            if has_more:
                page_num += 1
            await asyncio.sleep(0.6)

        await browser.close()

    return events
