"""The agent's memory — a tiny JSON file, keyed by user.

Not a new service and not a new database: just remembered preferences like
"doesn't like frocks". Kept deliberately small and dependency-free so the
agent runs on its own. Can be swapped for a wardrobe-DB table later without
changing the callers (same get/add functions).

Shape on disk:
    { "<user_id>": { "dislikes": ["frocks", "heels"], "notes": [...] } }
"""
import json
import os
import threading

from . import config

_lock = threading.Lock()


def _load() -> dict:
    try:
        with open(config.MEMORY_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save(data: dict) -> None:
    path = os.path.abspath(config.MEMORY_PATH)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)   # atomic: never leaves a half-written file


def get_prefs(user_id: str) -> dict:
    """Everything remembered about this user (empty dict if nothing yet)."""
    with _lock:
        return _load().get(user_id, {"dislikes": [], "notes": []})


def add_dislike(user_id: str, thing: str) -> dict:
    """Remember that the user dislikes `thing` (e.g. "frocks"). Idempotent."""
    thing = (thing or "").strip().lower()
    with _lock:
        data = _load()
        user = data.setdefault(user_id, {"dislikes": [], "notes": []})
        if thing and thing not in user["dislikes"]:
            user["dislikes"].append(thing)
        _save(data)
        return user


def is_disliked(prefs: dict, item: dict) -> bool:
    """Does this wardrobe item trip any remembered dislike?

    Matches a dislike word against the item's category/style/color so
    "frocks" filters out a Dress, "heels" filters out Heels, etc.
    """
    dislikes = [d for d in (prefs or {}).get("dislikes", []) if d]
    if not dislikes:
        return False
    # Build a haystack of the item's describable fields.
    parts: list[str] = []
    for key in ("category", "style", "pattern", "material"):
        v = item.get(key)
        if isinstance(v, str):
            parts.append(v.lower())
    for key in ("color", "occasion", "season"):
        v = item.get(key)
        if isinstance(v, list):
            parts.extend(str(x).lower() for x in v)
        elif isinstance(v, str):
            parts.append(v.lower())
    hay = " ".join(parts)
    for d in dislikes:
        # "frocks" should match "frock"/"dress"; handle the common plural.
        needle = d.rstrip("s")
        if needle and (needle in hay or d in hay):
            return True
        if d in ("frock", "frocks") and "dress" in hay:
            return True
    return False
