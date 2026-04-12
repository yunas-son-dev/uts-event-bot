"""
scraper.py — main orchestrator for GitHub Actions.

Runs both scrapers, deduplicates, sends to Discord webhooks, and posts
an admin summary.  Pass --dry-run to print everything without sending
or updating the JSON files.

Usage:
    python scraper.py
    python scraper.py --dry-run
"""

import argparse
import asyncio
import os
import sys

import requests
from dotenv import load_dotenv

from bots.prosple import scrape_prosple_it
from bots.uts_events import format_discord_message, scrape_uts_events_week_next
from utils.dedupe import DEFAULT_EVENTS_PATH, DEFAULT_PROSPLE_PATH, load_sent, save_sent
from utils.notify import notify

load_dotenv()

EVENTS_WEBHOOK = os.getenv("EVENTS_WEBHOOK_URL")
PROSPLE_WEBHOOK = os.getenv("PROSPLE_WEBHOOK_URL")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _send_webhook(webhook_url: str, message: str) -> bool:
    """POST a single message to a Discord webhook. Returns True on success."""
    resp = requests.post(webhook_url, json={"content": message}, timeout=10)
    if resp.status_code == 204:
        return True
    print(f"[scraper] Webhook error {resp.status_code}: {resp.text}")
    return False


def _send_all(webhook_url: str, messages: list[str], dry_run: bool) -> int:
    """Send a list of chunked messages. Returns count of messages sent."""
    sent = 0
    for msg in messages:
        if dry_run:
            print(msg)
            print("---")
            sent += 1
        else:
            if _send_webhook(webhook_url, msg):
                sent += 1
    return sent


def _chunk_prosple(items: list[tuple]) -> list[str]:
    """Format Prosple job tuples into <=1900-char Discord messages."""
    if not items:
        return ["**🚀 New IT Roles (Prosple)**\n\n😌 No new jobs this week."]

    header = "**🚀 New IT Roles (Prosple)**\n\n"
    chunks: list[str] = []
    cur = header

    for company, role, location, salary, start_date, link in items:
        sal_part = f" | 💰 {salary}" if salary else ""
        block = (
            f"🏢 **{company}** 🔗 <{link}>\n"
            f"💼 {role}\n"
            f"📍 {location}{sal_part}\n"
            f"{'—' * 30}\n\n"
        )
        if len(cur) + len(block) > 1900:
            chunks.append(cur)
            cur = block
        else:
            cur += block

    if cur.strip():
        chunks.append(cur)
    return chunks


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def run(dry_run: bool) -> None:
    events_sent = events_skipped = 0
    jobs_sent = jobs_skipped = 0
    errors: list[str] = []

    # --- UTS Events ---
    print("[scraper] Running uts_events scraper...")
    try:
        raw_events = await scrape_uts_events_week_next()
    except asyncio.TimeoutError:
        msg = "uts_events scraper timed out (>5 min)"
        print(f"[scraper] ERROR: {msg}")
        errors.append(msg)
        raw_events = []

    sent_events = load_sent(DEFAULT_EVENTS_PATH)
    fresh_events: list[tuple] = []
    new_event_keys: list[str] = []

    for date_str, title, desc, link in raw_events:
        key = link or f"{date_str}|{title}"
        if key in sent_events:
            events_skipped += 1
        else:
            fresh_events.append((date_str, title, desc, link))
            new_event_keys.append(key)

    print(f"[scraper] Events: {len(fresh_events)} new, {events_skipped} dupes")

    if EVENTS_WEBHOOK or dry_run:
        messages = format_discord_message(fresh_events)
        webhook = EVENTS_WEBHOOK or ""
        n = _send_all(webhook, messages, dry_run)
        events_sent = len(fresh_events)
        if not dry_run and n == len(messages):
            for k in new_event_keys:
                sent_events.add(k)
            save_sent(sent_events, DEFAULT_EVENTS_PATH)
    else:
        print("[scraper] EVENTS_WEBHOOK_URL not set – skipping.")

    # --- Prosple Jobs ---
    print("[scraper] Running prosple scraper...")
    try:
        raw_jobs = await asyncio.wait_for(scrape_prosple_it(), timeout=300)
    except asyncio.TimeoutError:
        msg = "prosple scraper timed out (>5 min)"
        print(f"[scraper] ERROR: {msg}")
        errors.append(msg)
        raw_jobs = []

    sent_prosple = load_sent(DEFAULT_PROSPLE_PATH)
    fresh_jobs: list[tuple] = []
    new_job_keys: list[str] = []

    for company, role, location, salary, start_date, link in raw_jobs:
        key = link or f"{company}|{role}"
        if key in sent_prosple:
            jobs_skipped += 1
        else:
            fresh_jobs.append((company, role, location, salary, start_date, link))
            new_job_keys.append(key)

    print(f"[scraper] Jobs: {len(fresh_jobs)} new, {jobs_skipped} dupes")

    if PROSPLE_WEBHOOK or dry_run:
        messages = _chunk_prosple(fresh_jobs)
        webhook = PROSPLE_WEBHOOK or ""
        n = _send_all(webhook, messages, dry_run)
        jobs_sent = len(fresh_jobs)
        if not dry_run and n == len(messages):
            for k in new_job_keys:
                sent_prosple.add(k)
            save_sent(sent_prosple, DEFAULT_PROSPLE_PATH)
    else:
        print("[scraper] PROSPLE_WEBHOOK_URL not set – skipping.")

    # --- Admin summary ---
    skipped_total = events_skipped + jobs_skipped
    summary = (
        f"✅ Sent {events_sent} events, {jobs_sent} jobs. "
        f"Skipped {skipped_total} dupes."
    )
    if errors:
        summary += "\n⚠️ Errors:\n" + "\n".join(f"  • {e}" for e in errors)

    print(f"[scraper] Summary: {summary}")

    if dry_run:
        print("[scraper] DRY RUN complete – nothing was sent or saved.")
    else:
        notify(summary)

    if errors:
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run all Discord event scrapers.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print output without sending webhooks or updating sent JSON files.",
    )
    args = parser.parse_args()
    asyncio.run(run(args.dry_run))


if __name__ == "__main__":
    main()
