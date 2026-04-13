"""
scraper.py — main orchestrator for GitHub Actions weekly run.

Runs:
  1. UTS Events (activateuts.com.au) → #uts-이벤트 webhook
  2. Prosple IT jobs (Sydney)        → #채용정보 webhook

Deduplicates against GitHub Gist (sent_events.json / sent_prosple.json).
Sends admin summary to ADMIN_WEBHOOK_URL.

Usage:
  python scraper.py            # live run
  python scraper.py --dry-run  # print only, no webhook / no Gist update
"""

import argparse
import asyncio
import os
import sys
import pathlib
import re

import requests
from dotenv import load_dotenv

load_dotenv()

# path setup so scraper.py (root) can import from utils/ and bots/
sys.path.insert(0, str(pathlib.Path(__file__).parent / "utils"))
sys.path.insert(0, str(pathlib.Path(__file__).parent / "bots"))

from dedupe import (
    load_sent_events,
    save_sent_events,
    load_sent_prosple,
    save_sent_prosple,
)
from notify import notify
from prosple import scrape_prosple_it
from uts_events import format_discord_message, scrape_uts_events_week_next

EVENTS_WEBHOOK_URL = os.getenv("EVENTS_WEBHOOK_URL")
PROSPLE_WEBHOOK_URL = os.getenv("PROSPLE_WEBHOOK_URL")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _post(webhook_url: str, message: str) -> bool:
    try:
        resp = requests.post(
            webhook_url,
            json={"content": message},
            timeout=10,
        )
        return resp.status_code == 204
    except Exception as e:
        print(f"[scraper] Webhook error: {e}")
        return False


def _send_messages(
    webhook_url: str | None,
    messages: list[str],
    dry_run: bool,
) -> int:
    if not messages:
        return 0

    if dry_run or not webhook_url:
        for m in messages:
            print(m)
            print("---")
        return len(messages)

    sent = 0
    for m in messages:
        if _post(webhook_url, m):
            sent += 1
        else:
            print("[scraper] Failed to send message chunk.")

    return sent


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------

async def run_events(dry_run: bool) -> tuple[int, int]:
    print("[scraper] --- UTS Events ---")
    sent_keys = load_sent_events()

    try:
        events = await scrape_uts_events_week_next()
    except asyncio.TimeoutError:
        print("[scraper] UTS Events scrape timed out.")
        notify("❌ UTS Events scrape timed out.")
        return 0, 0

    print(f"[scraper] Scraped {len(events)} events total.")

    # ✅ keep original parser untouched
    # apply single-day display policy only here
    single_day_events = [
        e for e in events
        if "-" not in e[0] and "–" not in e[0]
    ]
        print(
        f"[scraper] Filtered to {len(single_day_events)} "
        f"single-day events."
    )

    new_events = [e for e in single_day_events if e[3] not in sent_keys]
    skipped = len(single_day_events) - len(new_events)

    print(f"[scraper] New: {len(new_events)}, Skipped (dupe): {skipped}")

    if new_events:
        messages = format_discord_message(new_events)
        _send_messages(EVENTS_WEBHOOK_URL, messages, dry_run)

        if not dry_run:
            sent_keys.update(e[3] for e in new_events)
            save_sent_events(sent_keys)

    return len(new_events), skipped


# ---------------------------------------------------------------------------
# Prosple
# ---------------------------------------------------------------------------

async def run_prosple(dry_run: bool) -> tuple[int, int]:
    print("[scraper] --- Prosple Jobs ---")
    sent_keys = load_sent_prosple()

    try:
        jobs = await asyncio.wait_for(scrape_prosple_it(), timeout=300)
    except asyncio.TimeoutError:
        print("[scraper] Prosple scrape timed out.")
        notify("❌ Prosple scrape timed out.")
        return 0, 0

    print(f"[scraper] Scraped {len(jobs)} jobs total.")

    new_jobs = [j for j in jobs if j[5] not in sent_keys]
    skipped = len(jobs) - len(new_jobs)

    print(f"[scraper] New: {len(new_jobs)}, Skipped (dupe): {skipped}")

    if new_jobs:
        messages = _format_jobs(new_jobs)
        _send_messages(PROSPLE_WEBHOOK_URL, messages, dry_run)

        if not dry_run:
            sent_keys.update(j[5] for j in new_jobs)
            save_sent_prosple(sent_keys)

    return len(new_jobs), skipped


def _format_jobs(jobs: list[tuple]) -> list[str]:
    if not jobs:
        return []

    header = "**💼 New IT Graduate Jobs & Internships in Sydney!**\n\n"
    chunks: list[str] = []
    cur = header

    for company, role, location, salary, start_date, link in jobs:
        block = f"🏢 **{company}** | {role}\n"

        if location:
            block += f"📍 {location}\n"
        if salary:
            block += f"💰 {salary}\n"
        if start_date:
            block += f"🗓 Start: {start_date}\n"

        block += f"🔗 <{link}>\n\n"

        if len(cur) + len(block) > 1900:
            chunks.append(cur)
            cur = header + block
        else:
            cur += block

    if cur.strip():
        chunks.append(cur)

    return chunks


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main(dry_run: bool) -> None:
    print(f"[scraper] Starting. dry_run={dry_run}")

    events_new, events_skip = await run_events(dry_run)
    jobs_new, jobs_skip = await run_prosple(dry_run)

    summary = (
        f"{'[DRY RUN] ' if dry_run else ''}✅ Weekly scrape done.\n"
        f"Events — sent: {events_new}, dupes skipped: {events_skip}\n"
        f"Jobs   — sent: {jobs_new}, dupes skipped: {jobs_skip}"
    )

    print(f"\n[scraper] {summary}")
    notify(summary)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print output only; do not send webhooks or update Gist.",
    )
    args = parser.parse_args()
    asyncio.run(main(args.dry_run))