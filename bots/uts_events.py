import asyncio
import os
import re
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

BASE_URL = "https://www.activateuts.com.au/events/?orderby=featured"
CARDS_SELECTOR = "div.tile.tile--event"
SCRAPE_TIMEOUT = 300  # 5 minutes
MAX_PAGES = 10  # Hard cap — site may return the same page indefinitely

DATE_RE = re.compile(
    r"(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)",
    re.I,
)
MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


def _sydney_today() -> date:
    return datetime.now(ZoneInfo("Australia/Sydney")).date()


def _next_week_range_sydney() -> tuple[date, date]:
    """Next Monday .. Sunday in Australia/Sydney."""
    today = _sydney_today()
    this_monday = today - timedelta(days=today.weekday())
    next_monday = this_monday + timedelta(days=7)
    next_sunday = next_monday + timedelta(days=6)
    return next_monday, next_sunday


def _parse_dates(text: str) -> list[date]:
    """Extract all recognisable dates from a string."""
    today = _sydney_today()
    results = []
    for m in DATE_RE.finditer(text):
        day = int(m.group(1))
        mon = MONTHS[m.group(2).lower()]
        year = today.year
        try:
            d = date(year, mon, day)
            # If the parsed date is more than 6 months in the past, assume next year.
            if (d - today).days < -180:
                d = date(year + 1, mon, day)
            results.append(d)
        except ValueError:
            pass
    return results


async def _scrape() -> list[tuple[str, str, str, str]]:
    events: list[tuple[str, str, str, str]] = []
    start_of_week, end_of_week = _next_week_range_sydney()
    today = _sydney_today()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            page_num = 1
            prev_first_url: str | None = None

            while True:
                if page_num > MAX_PAGES:
                    print(f"[uts_events] MAX_PAGES ({MAX_PAGES}) reached – stopping.")
                    break
                # The Events Calendar supports ?tribe_paged=N; fall back to page_num
                if page_num == 1:
                    url = BASE_URL
                else:
                    url = f"{BASE_URL}&tribe_paged={page_num}"

                page = await browser.new_page()
                try:
                    await page.goto(url, timeout=30_000, wait_until="domcontentloaded")
                    try:
                        await page.wait_for_load_state("networkidle", timeout=8_000)
                    except PlaywrightTimeout:
                        pass

                    cards = page.locator(CARDS_SELECTOR)
                    count = await cards.count()
                    print(f"[uts_events] Page {page_num}: {count} cards")

                    if count == 0:
                        print("[uts_events] No cards – stopping pagination.")
                        break

                    # Detect when the site returns the same page repeatedly
                    # (tribe_paged= is ignored by some WordPress themes).
                    first_url_el = cards.nth(0).locator("a[href*='/events/']").first
                    curr_first_url = (
                        await first_url_el.get_attribute("href") or ""
                        if await first_url_el.count() else ""
                    )
                    if curr_first_url and curr_first_url == prev_first_url:
                        print(
                            f"[uts_events] Page {page_num} repeats page {page_num - 1} "
                            f"– pagination exhausted, stopping."
                        )
                        break
                    prev_first_url = curr_first_url

                    all_past_end = True

                    for i in range(count):
                        card = cards.nth(i)
                        try:
                            # --- Link ---
                            link = ""
                            link_el = card.locator("a[href*='/events/']").first
                            if await link_el.count():
                                href = await link_el.get_attribute("href") or ""
                                link = (
                                    href
                                    if href.startswith("http")
                                    else f"https://www.activateuts.com.au{href}"
                                )

                            # --- Title ---
                            title = ""
                            for sel in [
                                "h3", "h2",
                                ".tile__title", ".tile__name",
                                "[class*='title']",
                            ]:
                                el = card.locator(sel).first
                                if await el.count():
                                    title = (await el.inner_text()).strip()
                                    if title:
                                        break

                            if not title:
                                continue

                            # --- Date text ---
                            date_text = ""
                            for sel in [
                                ".tile__badge",          # e.g. "9 FEB - 8 JUN" or "16 APR"
                                "time",
                                ".tribe-event-date-start",
                                ".tile__date",
                                "[class*='date']",
                                "[class*='when']",
                            ]:
                                el = card.locator(sel).first
                                if await el.count():
                                    date_text = (await el.inner_text()).strip()
                                    if date_text:
                                        break
                            if not date_text:
                                date_text = await card.inner_text()
                            print(
                                f"[uts_events] Page {page_num} card {i}: "
                                f"date_text={date_text!r}"
                            )

                            # --- Description ---
                            desc = ""
                            for sel in [
                                ".tile__excerpt", ".tile__summary", "p"
                            ]:
                                el = card.locator(sel).first
                                if await el.count():
                                    candidate = (await el.inner_text()).strip()
                                    if candidate and candidate != title:
                                        desc = candidate
                                        break

                            # --- Date filtering ---
                            dates = _parse_dates(date_text)
                            print(
                                f"[uts_events] Page {page_num} card {i}: "
                                f"parsed dates={dates}"
                            )
                            if not dates:
                                continue

                            event_start = min(dates)
                            event_end = max(dates)

                            # Stop-condition guard: only count events that started
                            # recently (within 7 days) or are upcoming.
                            # Semester-long programs (e.g. "9 FEB – 8 JUN") have
                            # stale start dates and appear pinned on every page;
                            # letting them set all_past_end=False causes infinite
                            # pagination since their event_start is always <= end_of_week.
                            recently_or_upcoming = event_start > today - timedelta(days=7)
                            if recently_or_upcoming and event_start <= end_of_week:
                                all_past_end = False

                            # Keep only events that overlap next week
                            if event_start <= end_of_week and event_end >= start_of_week:
                                if event_start == event_end:
                                    date_str = event_start.strftime("%-d %b")
                                else:
                                    date_str = (
                                        f"{event_start.strftime('%-d %b')}"
                                        f" – {event_end.strftime('%-d %b')}"
                                    )
                                events.append((date_str, title, desc, link))

                        except Exception as e:
                            print(f"[uts_events] Card {i} error: {e}")
                            continue

                    if all_past_end:
                        print("[uts_events] All cards past end of next week – stopping.")
                        break

                    page_num += 1

                finally:
                    await page.close()

        finally:
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
            cur = block
        else:
            cur += block

    if cur.strip():
        chunks.append(cur)
    return chunks


if __name__ == "__main__":
    import requests
    from dotenv import load_dotenv

    load_dotenv()
    webhook_url = os.environ.get("EVENTS_WEBHOOK_URL")

    events = asyncio.run(scrape_uts_events_week_next())
    print(f"[uts_events] {len(events)} events for next week")
    for e in events:
        print(f"  {e[0]} | {e[1]} | {e[3]}")

    if webhook_url:
        for msg in format_discord_message(events):
            resp = requests.post(webhook_url, json={"content": msg})
            if resp.status_code == 204:
                print("[uts_events] Sent.")
            else:
                print(f"[uts_events] Send failed: {resp.status_code} {resp.text}")
    else:
        print("[uts_events] EVENTS_WEBHOOK_URL not set – skipping send.")
