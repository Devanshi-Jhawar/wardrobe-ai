"""Turn a wardrobe item's free-form `category` into a wardrobe *slot*.

An outfit is built from slots (one top, one bottom, shoes, ...), but the
wardrobe stores specific categories ("Tshirts", "Jeans", "Heels"). This maps
one to the other so the composer can reason about "do I have a bottom?".
"""

# slot -> keywords that place a category in that slot (checked in this order,
# so more specific slots like "onepiece"/"outerwear" come before "top").
SLOT_KEYWORDS = {
    "onepiece":  ["dress", "gown", "saree", "sari", "jumpsuit", "kurta set", "lehenga", "frock"],
    "outerwear": ["jacket", "blazer", "coat", "overcoat", "hoodie"],
    "top":       ["shirt", "tshirt", "t-shirt", "top", "kurta", "sweater",
                  "sweatshirt", "blouse", "tank", "tee"],
    "bottom":    ["jeans", "trouser", "pant", "chino", "short", "skirt",
                  "legging", "palazzo", "track"],
    "footwear":  ["shoe", "sneaker", "heel", "sandal", "flip", "flat",
                  "loafer", "boot", "slipper"],
    "accessory": ["watch", "belt", "sunglass", "bag", "scarf", "cap",
                  "hat", "jewel", "earring", "necklace"],
}

# The slots a complete outfit needs, by situation.
CORE_SLOTS = ["top", "bottom", "footwear"]   # a onepiece replaces top+bottom


def slot_of(category: str | None) -> str | None:
    """Best-guess slot for a category string, or None if unrecognised."""
    if not category:
        return None
    c = category.lower()
    for slot, words in SLOT_KEYWORDS.items():
        if any(w in c for w in words):
            return slot
    return None


def group_by_slot(items: list[dict]) -> dict[str, list[dict]]:
    """Bucket wardrobe items by slot. Items with an unknown category are dropped."""
    buckets: dict[str, list[dict]] = {}
    for it in items:
        s = slot_of(it.get("category"))
        if s:
            buckets.setdefault(s, []).append(it)
    return buckets
