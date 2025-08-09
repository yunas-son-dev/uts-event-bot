# utils/dedupe.py
import json, os
from typing import Set

DEFAULT_PATH = "sent/sent_events.json"

def load_sent(path: str = DEFAULT_PATH) -> Set[str]:
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        return set()
    with open(path, "r", encoding="utf-8") as f:
        try:
            return set(json.load(f))
        except Exception:
            return set()

def save_sent(keys: Set[str], path: str = DEFAULT_PATH) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(sorted(list(keys)), f, ensure_ascii=False, indent=2)
