async def run_events(dry_run: bool) -> tuple[int, int]:
    print("[scraper] --- UTS Events ---")
    sent_keys = load_sent_events()

    try:
        events = await scrape_uts_events_week_next()
    except asyncio.TimeoutError:
        print("[scraper] UTS Events scrape timed out.")
        notify("❌ UTS Events scrape timed out.")
        return 0, 0

    # ✅ keep original scrape logic, exclude long-range display dates here only
    events = [e for e in events if "-" not in e[0] and "–" not in e[0]]

    print(f"[scraper] Scraped {len(events)} single-day events total.")

    new_events = [e for e in events if e[3] not in sent_keys]
    skipped = len(events) - len(new_events)

    print(f"[scraper] New: {len(new_events)}, Skipped (dupe): {skipped}")

    if new_events:
        messages = format_discord_message(new_events)
        _send_messages(EVENTS_WEBHOOK_URL, messages, dry_run)

        if not dry_run:
            sent_keys.update(e[3] for e in new_events)
            save_sent_events(sent_keys)

    return len(new_events), skipped