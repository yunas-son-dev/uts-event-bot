# acad_calendar.py
"""
Scrapes the UTS Principal Dates page and posts this month's events to Discord.

Page structure: one <h3 class="sans-serif-heading"> per month, followed
immediately by a <table> with DATE | WHAT'S ON columns.
No JavaScript / Playwright required — plain requests + BeautifulSoup.

Usage:
    python bots/acad_calendar.py
    python bots/acad_calendar.py --dry-run
"""

import argparse
import os
import sys
from datetime import datetime

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

YEAR = datetime.now().year
URL = (
    f"https://www.uts.edu.au/for-students/current-students/"
    f"managing-your-course/important-dates/principal-dates/"
    f"{YEAR}-principal-dates"
)


def fetch_month_events(month_name: str) -> list[dict]:
    """
    Fetch all DATE/WHAT'S ON rows for *month_name* (e.g. "April")
    from the UTS Principal Dates page.
    Returns a list of {"date": str, "event": str} dicts.
    """
    resp = requests.get(URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")

    # Find the <h3> whose text starts with the target month name
    target_h3 = None
    for h3 in soup.find_all("h3", class_="sans-serif-heading"):
        if h3.get_text(strip=True).startswith(month_name):
            target_h3 = h3
            break

    if target_h3 is None:
        print(f"[acad_calendar] No heading found for '{month_name}' on {URL}")
        return []

    # The month table is the first <table> after that heading
    table = target_h3.find_next("table")
    if table is None:
        print(f"[acad_calendar] No table found after '{month_name}' heading")
        return []

    events: list[dict] = []
    for row in table.find_all("tr"):
        cols = row.find_all("td")
        if len(cols) < 2:
            continue  # skip header row (th) and malformed rows
        date_text = cols[0].get_text(separator=" ", strip=True)
        event_text = cols[1].get_text(separator=" ", strip=True)
        if date_text and event_text:
            events.append({"date": date_text, "event": event_text})

    return events


def build_message(events: list[dict], year: int, month_name: str) -> str:
    if not events:
        return (
            f"📅 {year}년 {month_name} UTS Principal Dates 📅\n\n"
            "이번 달에는 등록된 학사 일정이 없습니다."
        )
    lines = [f"📅 {year}년 {month_name} UTS Principal Dates 📅\n"]
    for e in events:
        lines.append(f"- {e['date']}일: {e['event']}")
    return "\n".join(lines)


def send_discord(message: str) -> bool:
    """POST to ACADEMIC_WEBHOOK_URL. Returns True on success."""
    webhook_url = os.environ.get("ACADEMIC_WEBHOOK_URL")
    if not webhook_url:
        print("[acad_calendar] ACADEMIC_WEBHOOK_URL not set.")
        return False
    # Discord limit: 2000 chars. Truncate with a note rather than silently dropping.
    if len(message) > 1990:
        message = message[:1987] + "..."
    resp = requests.post(webhook_url, json={"content": message}, timeout=10)
    if resp.status_code == 204:
        print("[acad_calendar] Message sent.")
        return True
    print(f"[acad_calendar] Send failed: {resp.status_code} {resp.text}")
    return False


def main() -> None:
    # Ensure UTF-8 output on Windows terminals that default to CP1252.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(
        description="Post UTS principal dates for this month to Discord."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the message instead of sending it.",
    )
    args = parser.parse_args()

    now = datetime.now()
    month_name = now.strftime("%B")  # e.g. "April"

    try:
        events = fetch_month_events(month_name)
    except Exception as e:
        print(f"[acad_calendar] Fetch error: {e}")
        sys.exit(1)

    msg = build_message(events, now.year, month_name)
    print(f"[acad_calendar] {len(events)} events for {month_name} {now.year}")

    if args.dry_run:
        print("--- DRY RUN ---")
        print(msg)
        return

    if not send_discord(msg):
        sys.exit(1)


if __name__ == "__main__":
    main()
