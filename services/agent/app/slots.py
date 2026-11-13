"""The agent's clothing vocabulary: wardrobe category -> outfit slot + weather words.

Three services name clothes differently:
  - vision tags uploads with the 23 classes of its YOLO model (data.yaml):
    "Kurti", "Sharara", "Anarkali", ...
  - weather describes needs in its own words (weather/main.py TYPES):
    "kurta", "trousers", "sandals", ...
  - users can also type any category by hand ("Tshirts", "Heels").

CATEGORIES is the bridge. For every vision class it says which outfit slot the
item fills and which weather words describe it, so the composer can match
"avoid boots, prefer sandals" against what the user owns. Categories not in
the table fall back to keyword matching (SLOT_KEYWORDS / WEATHER_KEYWORDS).
tests/test_vocabulary.py fails if a vision class or weather word is unmapped.
"""

# category (lowercase) -> (slot, weather words)
# Slots: top, bottom, onepiece (replaces top + bottom), footwear, outerwear,
#        accessory (added on top of a complete outfit).
CATEGORIES: dict[str, tuple[str, list[str]]] = {
    # --- the 23 vision classes ---
    "anarkali":   ("onepiece",  ["dress", "kurta"]),   # long flared kurta, worn as a full outfit
    "bag":        ("accessory", []),
    "blazer":     ("outerwear", ["jacket"]),
    "dress":      ("onepiece",  ["dress"]),
    "dupatta":    ("accessory", []),                    # stole worn with ethnic outfits
    "hoodie":     ("outerwear", ["hoodie"]),
    "jacket":     ("outerwear", ["jacket"]),
    "jeans":      ("bottom",    ["jeans"]),
    "jewellery":  ("accessory", []),
    "kameez":     ("top",       ["kurta", "top"]),      # tunic of a shalwar kameez
    "kurti":      ("top",       ["kurta", "top"]),
    "lehenga":    ("onepiece",  ["dress", "skirt"]),
    "maxi":       ("onepiece",  ["dress"]),
    "saree":      ("onepiece",  ["dress"]),
    "shalwar":    ("bottom",    ["trousers"]),
    "sharara":    ("bottom",    ["trousers"]),
    "sherwani":   ("top",       ["kurta", "jacket"]),   # long coat, worn over a bottom
    "shirt":      ("top",       ["shirt"]),
    "shoes":      ("footwear",  ["shoes"]),
    "skirt":      ("bottom",    ["skirt"]),
    "slippers":   ("footwear",  ["sandals"]),
    "sunglasses": ("accessory", []),
    "t-shirt":    ("top",       ["t-shirt"]),
}

# Fallback for hand-typed categories: slot -> keywords, checked in this order
# (more specific slots first, so "kurta set" is a onepiece, not a top).
SLOT_KEYWORDS = {
    "onepiece":  ["dress", "gown", "saree", "sari", "jumpsuit", "kurta set", "lehenga",
                  "frock", "anarkali", "maxi", "salwar suit", "co-ord"],
    "outerwear": ["jacket", "blazer", "coat", "overcoat", "hoodie", "cardigan", "shrug"],
    "top":       ["shirt", "tshirt", "t-shirt", "top", "kurta", "kurti", "kameez", "sherwani",
                  "sweater", "sweatshirt", "blouse", "tank", "tee", "tunic", "polo"],
    "bottom":    ["jeans", "trouser", "pant", "chino", "short", "skirt", "legging",
                  "palazzo", "track", "shalwar", "salwar", "sharara", "churidar", "dhoti"],
    "footwear":  ["shoe", "sneaker", "heel", "sandal", "flip", "flat", "loafer", "boot",
                  "slipper", "jutti", "mojari", "kolhapuri"],
    "accessory": ["watch", "belt", "sunglass", "bag", "scarf", "cap", "hat", "jewel",
                  "earring", "necklace", "dupatta", "stole", "clutch", "bangle"],
}

# Fallback: weather word -> keywords that mean it in a hand-typed category.
WEATHER_KEYWORDS = {
    "t-shirt":  ["t-shirt", "tshirt", "tee"],
    "shirt":    ["shirt"],
    "top":      ["top", "blouse", "tank", "kurti", "kameez"],
    "kurta":    ["kurta", "kurti", "kameez", "anarkali", "sherwani"],
    "dress":    ["dress", "gown", "saree", "sari", "frock", "maxi", "lehenga", "jumpsuit"],
    "skirt":    ["skirt", "lehenga"],
    "shorts":   ["short"],
    "jeans":    ["jeans"],
    "trousers": ["trouser", "pant", "chino", "palazzo", "shalwar", "salwar", "sharara", "churidar"],
    "sweater":  ["sweater", "sweatshirt", "cardigan", "pullover"],
    "hoodie":   ["hoodie"],
    "jacket":   ["jacket", "blazer", "sherwani"],
    "coat":     ["coat", "overcoat"],
    "sandals":  ["sandal", "slipper", "flip", "kolhapuri"],
    "sneakers": ["sneaker"],
    "shoes":    ["shoe", "loafer", "heel", "flat", "jutti", "mojari"],
    "boots":    ["boot"],
}

# The slots a complete outfit needs (a onepiece replaces top + bottom).
CORE_SLOTS = ["top", "bottom", "footwear"]


def _key(category: str) -> str:
    c = category.strip().lower()
    if c in CATEGORIES:
        return c
    if c.endswith("s") and c[:-1] in CATEGORIES:   # "Kurtis", "Sarees"
        return c[:-1]
    return c


def slot_of(category: str | None) -> str | None:
    """Slot for a category string, or None if unrecognised."""
    if not category:
        return None
    c = _key(category)
    if c in CATEGORIES:
        return CATEGORIES[c][0]
    for slot, words in SLOT_KEYWORDS.items():
        if any(w in c for w in words):
            return slot
    return None


def weather_types_of(category: str | None) -> set[str]:
    """The weather service's words for this category ({"kurta", "top"} for Kurti)."""
    if not category:
        return set()
    c = _key(category)
    if c in CATEGORIES:
        return set(CATEGORIES[c][1])
    return {t for t, words in WEATHER_KEYWORDS.items() if any(w in c for w in words)}


def group_by_slot(items: list[dict]) -> dict[str, list[dict]]:
    """Bucket wardrobe items by slot. Items with an unknown category are dropped."""
    buckets: dict[str, list[dict]] = {}
    for it in items:
        s = slot_of(it.get("category"))
        if s:
            buckets.setdefault(s, []).append(it)
    return buckets
