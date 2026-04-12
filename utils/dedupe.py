# utils/dedupe.py
"""
Deduplication store backed by a GitHub Gist.

Required env vars:
  GIST_TOKEN  — personal access token with 'gist' scope
  GIST_ID     — ID of the gist containing sent_events.json / sent_prosple.json
"""

import json
import os
from typing import Set

import requests

GIST_TOKEN = os.getenv("GIST_TOKEN")
GIST_ID = os.getenv("GIST_ID")

EVENTS_FILE = "sent_events.json"
PROSPLE_FILE = "sent_prosple.json"


def _headers() -> dict:
    return {
        "Authorization": f"token {GIST_TOKEN}",
        "Accept": "application/vnd.github+json",
    }


def _gist_available() -> bool:
    return bool(GIST_TOKEN and GIST_ID)


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
        return set(json.loads(content))
    except Exception as e:
        print(f"[dedupe] Failed to load {filename} from Gist: {e}")
        return set()


def _save(keys: Set[str], filename: str) -> None:
    if not _gist_available():
        print(f"[dedupe] Gist not configured, skipping save for {filename}")
        return
    try:
        payload = {
            "files": {
                filename: {
                    "content": json.dumps(sorted(list(keys)), ensure_ascii=False, indent=2)
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
        print(f"[dedupe] Saved {len(keys)} keys to Gist:{filename}")
    except Exception as e:
        print(f"[dedupe] Failed to save {filename} to Gist: {e}")


def load_sent_events() -> Set[str]:
    return _load(EVENTS_FILE)


def load_sent_prosple() -> Set[str]:
    return _load(PROSPLE_FILE)


def save_sent_events(keys: Set[str]) -> None:
    _save(keys, EVENTS_FILE)


def save_sent_prosple(keys: Set[str]) -> None:
    _save(keys, PROSPLE_FILE)