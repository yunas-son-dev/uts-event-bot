# acad_calendar.py
import argparse
import os
import sys
import requests
from datetime import datetime
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
from dotenv import load_dotenv

load_dotenv()

YEAR = datetime.now().year
URL = (
    f"https://www.uts.edu.au/for-students/current-students/"
    f"managing-your-course/important-dates/academic-year-dates/"
    f"{YEAR}-academic-year-dates"
)

SEMESTERS = {
    "Autumn": "collapsible-0",
    "Spring": "collapsible-1",
    "Summer": "collapsible-2",
}

MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
}


def parse_date_range(date_str: str):
    date_str = date_str.lower()
    months_in_text = [MONTHS[m] for m in MONTHS if m in date_str]
    if not months_in_text:
        return None
    return months_in_text[0], months_in_text[-1]


def fetch_all_events() -> list[dict]:
    """Scrape all semester events from the UTS academic calendar page."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.goto(URL, timeout=30_000, wait_until="domcontentloaded")

            for sem_name, sem_id in SEMESTERS.items():
                # Click the collapsible toggle (button that controls the section)
                # The UTS site uses aria-controls or data-target to link toggle -> panel
                try:
                    toggle = page.locator(
                        f"[aria-controls='{sem_id}'], "
                        f"button[data-target='#{sem_id}'], "
                        f"[data-toggle='collapse'][href='#{sem_id}']"
                    ).first
                    if toggle.count():
                        toggle.click()
                    else:
                        # Fallback: click the collapsible div itself if it has a heading
                        page.locator(f"#{sem_id}").first.click()
                except Exception as e:
                    print(f"[acad_calendar] Could not click toggle for {sem_name}: {e}")

                # Wait for a table to become visible inside this collapsible
                try:
                    page.wait_for_selector(
                        f"#{sem_id} table",
                        state="visible",
                        timeout=5_000,
                    )
                except PlaywrightTimeout:
                    # Fallback: wait 2s and hope content is now in the DOM
                    page.wait_for_timeout(2_000)

            html = page.content()
        finally:
            browser.close()

    soup = BeautifulSoup(html, "html.parser")
    events: list[dict] = []

    for sem_name, sem_id in SEMESTERS.items():
        collapsible = soup.find("div", id=sem_id)
        if not collapsible:
            print(f"[acad_calendar] Section not found: #{sem_id}")
            continue

        tables = collapsible.find_all("table")
        if not tables:
            print(f"[acad_calendar] No tables found in #{sem_id} – collapsible may not have expanded")

        for table in tables:
            for row in table.find_all("tr"):
                cols = row.find_all("td")
                if len(cols) != 2:
                    continue
                event_name = cols[0].get_text(strip=True)
                date_range = cols[1].get_text(strip=True)
                parsed_range = parse_date_range(date_range)
                events.append({
                    "session": sem_name,
                    "event": event_name,
                    "date_range": date_range,
                    "month_range": parsed_range,
                })

    return events


def get_events_for_month(events: list[dict], month: int) -> list[dict]:
    """Filter to events that cover the given month number."""
    result = []
    for e in events:
        if not e["month_range"]:
            continue
        start, end = e["month_range"]
        if start <= month <= end:
            result.append(e)
    return result


def build_message(month_events: list[dict], year: int, month_name: str) -> str:
    if not month_events:
        return (
            f"📅 {year}년 {month_name} UTS Academic Events 📅\n\n"
            "이번 달에는 등록된 학사 일정이 없습니다."
        )
    lines = [f"📅 {year}년 {month_name} UTS Academic Events 📅\n"]
    for e in month_events:
        lines.append(f"- [{e['session']}] {e['event']}: {e['date_range']}")
    return "\n".join(lines)


def send_discord_via_webhook(message: str) -> bool:
    """Post message to ACADEMIC_WEBHOOK_URL. Returns True on success."""
    webhook_url = os.environ.get("ACADEMIC_WEBHOOK_URL")
    if not webhook_url:
        print("[acad_calendar] ACADEMIC_WEBHOOK_URL not set.")
        return False
    resp = requests.post(webhook_url, json={"content": message})
    if resp.status_code == 204:
        print("[acad_calendar] Message sent.")
        return True
    print(f"[acad_calendar] Send failed: {resp.status_code} {resp.text}")
    return False


def main():
    parser = argparse.ArgumentParser(description="Post UTS academic calendar to Discord.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the message instead of sending it.",
    )
    args = parser.parse_args()

    now = datetime.now()
    all_events = fetch_all_events()
    month_events = get_events_for_month(all_events, now.month)
    msg = build_message(month_events, now.year, now.strftime("%B"))

    if args.dry_run:
        print("--- DRY RUN ---")
        print(msg)
        return

    success = send_discord_via_webhook(msg)
    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
