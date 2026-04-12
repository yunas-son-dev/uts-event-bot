# utils/dedupe.py
import json
import os
from typing import Set

# Configurable via env vars so CI/CD can override without changing code.
DEFAULT_EVENTS_PATH = os.getenv("SENT_EVENTS_PATH", "sent/sent_events.json")
DEFAULT_PROSPLE_PATH = os.getenv("SENT_PROSPLE_PATH", "sent/sent_prosple.json")

# Keep the generic DEFAULT_PATH pointing at events for backwards-compat.
DEFAULT_PATH = DEFAULT_EVENTS_PATH


def load_sent(path: str = DEFAULT_PATH) -> Set[str]:
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        return set()
    with open(path, "r", encoding="utf-8") as f:
        try:
            return set(json.load(f))
        except Exception:
            return set()


def save_sent(keys: Set[str], path: str = DEFAULT_PATH) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(sorted(list(keys)), f, ensure_ascii=False, indent=2)
