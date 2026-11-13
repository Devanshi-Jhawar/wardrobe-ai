"""What the agent knows about a user's taste, and how it applies to items.

Storage lives in the memory service (port 8006); this module only turns its
`GET /memory/{user_id}` reply into a flat dict and answers "does this item
trip a like / dislike / recent wear?".

Shape used throughout the agent (all keys always present):
    {
      "available": bool,               # False if the memory service was down
      "likes": ["blue", "ethnic"],     # free words, matched against item fields
      "dislikes": ["frocks"],
      "liked_item_ids": [...],         # from thumbs-up feedback
      "disliked_item_ids": [...],      # from thumbs-down feedback
      "recently_worn_item_ids": [...], # worn within avoid_repeat_days
      "avoid_repeat_days": 3,
    }
"""


def empty_prefs(available: bool = False) -> dict:
    return {
        "available": available,
        "likes": [],
        "dislikes": [],
        "liked_item_ids": [],
        "disliked_item_ids": [],
        "recently_worn_item_ids": [],
        "avoid_repeat_days": None,
    }


def from_memory(memory: dict | None) -> dict:
    """Flatten the memory service's reply. None (service down) -> empty prefs."""
    if not memory:
        return empty_prefs(available=False)
    p = memory.get("preferences") or {}
    return {
        "available": True,
        "likes": [str(x).lower() for x in p.get("likes") or []],
        "dislikes": [str(x).lower() for x in p.get("dislikes") or []],
        "liked_item_ids": list(memory.get("liked_item_ids") or []),
        "disliked_item_ids": list(memory.get("disliked_item_ids") or []),
        "recently_worn_item_ids": list(memory.get("recently_worn_item_ids") or []),
        "avoid_repeat_days": p.get("avoid_repeat_days"),
    }


def haystack(item: dict) -> str:
    """The item's describable fields as one lowercase string."""
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
    return " ".join(parts)


def word_hits(words: list[str], hay: str) -> bool:
    for w in words:
        if not w:
            continue
        # "frocks" should match "frock"; handle the common plural.
        needle = w.rstrip("s")
        if (needle and needle in hay) or w in hay:
            return True
        if w in ("frock", "frocks") and "dress" in hay:
            return True
    return False


def is_disliked(prefs: dict | None, item: dict) -> bool:
    """A remembered dislike word matches the item, or it got a thumbs-down."""
    prefs = prefs or {}
    if item.get("id") and item["id"] in (prefs.get("disliked_item_ids") or []):
        return True
    return word_hits(prefs.get("dislikes") or [], haystack(item))


def is_liked(prefs: dict | None, item: dict) -> bool:
    """A like word matches the item, or it got a thumbs-up."""
    prefs = prefs or {}
    if item.get("id") and item["id"] in (prefs.get("liked_item_ids") or []):
        return True
    return word_hits(prefs.get("likes") or [], haystack(item))


def recently_worn(prefs: dict | None, item: dict) -> bool:
    return bool(item.get("id")) and item["id"] in ((prefs or {}).get("recently_worn_item_ids") or [])
