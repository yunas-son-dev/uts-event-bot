"""
Deduplication store backed by a GitHub Gist with 90-day retention.

Required env vars:
  GIST_TOKEN  — personal access token with 'gist' scope
  GIST_ID     — ID of the gist containing sent_events.json / sent_prosple.json
"""

import json
import os
from datetime import datetime, timedelta
from typing import Dict, Set

import requests

GIST_TOKEN = os.getenv("GIST_TOKEN")
GIST_ID = os.getenv("GIST_ID")

EVENTS_FILE = "sent_events.json"
PROSPLE_FILE = "sent_prosple.json"
RETENTION_DAYS = 90


def _headers() -> dict:
    return {
        "Authorization": f"token {GIST_TOKEN}",
        "Accept": "application/vnd.github+json",
    }


def _gist_available() -> bool:
    return bool(GIST_TOKEN and GIST_ID)


def _today_str() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d")


def _purge_old(data: Dict[str, str]) -> Dict[str, str]:
    cutoff = datetime.utcnow() - timedelta(days=RETENTION_DAYS)
    cleaned: Dict[str, str] = {}

    for key, date_str in data.items():
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            if dt >= cutoff:
                cleaned[key] = date_str
        except Exception:
            # malformed legacy value → drop
            continue

    return cleaned


def _load(filename: str) -> Set[str]:
    if not _gist_available():
        print(f"[dedupe] Gist not configured, returning empty set for {filename}")
        return set()

    try:
        resp = requests.get(
            f"https://api.github.com/gists/{GIST_ID}",
            headers=_headers(),
            timeout=10,
        )
        resp.raise_for_status()

        content = resp.json()["files"][filename]["content"]
        raw = json.loads(content)

        # ✅ legacy migration: old list[str] → dict[str, today]
        if isinstance(raw, list):
            today = _today_str()
            raw = {k: today for k in raw}

        if not isinstance(raw, dict):
            print(f"[dedupe] Unexpected format in {filename}, resetting.")
            return set()

        cleaned = _purge_old(raw)

        # optional self-healing save if old keys were removed
        if len(cleaned) != len(raw):
            _save_map(cleaned, filename)

        return set(cleaned.keys())

    except Exception as e:
        print(f"[dedupe] Failed to load {filename} from Gist: {e}")
        return set()


def _save_map(data: Dict[str, str], filename: str) -> None:
    if not _gist_available():
        print(f"[dedupe] Gist not configured, skipping save for {filename}")
        return

    try:
        payload = {
            "files": {
                filename: {
                    "content": json.dumps(
                        data,
                        ensure_ascii=False,
                        indent=2,
                        sort_keys=True,
                    )
                }
            }
        }

        resp = requests.patch(
            f"https://api.github.com/gists/{GIST_ID}",
            headers=_headers(),
            json=payload,
            timeout=10,
        )
        resp.raise_for_status()
        print(f"[dedupe] Saved {len(data)} keys to Gist: {filename}")

    except Exception as e:
        print(f"[dedupe] Failed to save {filename} to Gist: {e}")


def _save(keys: Set[str], filename: str) -> None:
    today = _today_str()

    # load existing timestamp map first
    existing_map: Dict[str, str] = {}

    try:
        resp = requests.get(
            f"https://api.github.com/gists/{GIST_ID}",
            headers=_headers(),
            timeout=10,
        )
        resp.raise_for_status()

        content = resp.json()["files"][filename]["content"]
        raw = json.loads(content)

        if isinstance(raw, list):
            existing_map = {k: today for k in raw}
        elif isinstance(raw, dict):
            existing_map = raw

    except Exception:
        pass

    # overwrite / refresh timestamps
    for key in keys:
        existing_map[key] = today

    cleaned = _purge_old(existing_map)
    _save_map(cleaned, filename)


def load_sent_events() -> Set[str]:
    return _load(EVENTS_FILE)


def load_sent_prosple() -> Set[str]:
    return _load(PROSPLE_FILE)


def save_sent_events(keys: Set[str]) -> None:
    _save(keys, EVENTS_FILE)


def save_sent_prosple(keys: Set[str]) -> None:
    _save(keys, PROSPLE_FILE)