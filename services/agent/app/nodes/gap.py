"""Node 5: gap — what the wardrobe is missing, and what to add.

Runs in two situations:
  - after a recommendation (or trip plan), to suggest pieces the user doesn't
    own that would make it better;
  - as the whole answer to a "what should I buy?" question.

Suggestions come from rules, in this order, each tagged with a `kind`:
  missing    a core slot the outfit couldn't fill at all (no footwear)
  occasion   the slot was filled, but nothing the user owns in it suits the
             occasion (only t-shirts for an office day)
  weather    gear the forecast calls for that the user doesn't own (a raincoat)
  complement a piece that finishes the chosen look (juttis with a kurti,
             a leather watch with a shirt), in a colour that goes with it
  coverage   (shopping questions only) occasions the wardrobe can't dress

Each one carries a reason, a shopping rule and a ready-made search link.
Links are generic shopping searches, not an affiliate feed; swap in a real
catalogue later without touching this logic. Anything the user has said they
dislike is never suggested.
"""
from urllib.parse import quote_plus

from .. import prefs as prefs_mod
from ..slots import group_by_slot, CORE_SLOTS, slot_of
from ..state import OutfitState
from .composer import _matches_occasion, _colors, day_plans

MAX_SUGGESTIONS = 6
MAX_COMPLEMENTS = 2

SLOT_LABEL = {
    "top": "top", "bottom": "bottom", "footwear": "footwear",
    "outerwear": "jacket or blazer", "onepiece": "dress or one-piece",
}
SLOT_PLURAL = {
    "top": "tops", "bottom": "bottoms", "footwear": "footwear",
    "outerwear": "jackets or blazers", "onepiece": "dresses or one-pieces",
}

# What to buy for a slot, given an occasion (else "<occasion> <slot>").
OCCASION_PIECES = {
    ("office", "top"): "formal shirt or kurta", ("office", "bottom"): "tailored trousers",
    ("office", "footwear"): "leather loafers or block heels",
    ("office", "outerwear"): "structured blazer",
    ("wedding", "onepiece"): "lehenga or silk saree", ("wedding", "top"): "embroidered kurta",
    ("wedding", "bottom"): "sharara or churidar", ("wedding", "footwear"): "embellished juttis",
    ("festival", "top"): "festive kurti", ("festival", "bottom"): "palazzo or sharara",
    ("festival", "onepiece"): "anarkali", ("festival", "footwear"): "kolhapuris or juttis",
    ("party", "top"): "satin or sequin top", ("party", "onepiece"): "cocktail dress",
    ("party", "footwear"): "heels or dress shoes", ("party", "bottom"): "tailored trousers",
    ("date", "top"): "silk blouse or smart shirt", ("date", "onepiece"): "midi dress",
    ("gym", "top"): "dri-fit t-shirt", ("gym", "bottom"): "track pants or leggings",
    ("gym", "footwear"): "running shoes",
    ("beach", "top"): "linen shirt or tank top", ("beach", "bottom"): "shorts",
    ("beach", "footwear"): "flip flops or sandals", ("beach", "onepiece"): "kaftan or sundress",
    ("hiking", "top"): "quick-dry t-shirt", ("hiking", "bottom"): "cargo or trekking pants",
    ("hiking", "footwear"): "trekking shoes", ("hiking", "outerwear"): "windcheater",
    ("sightseeing", "footwear"): "comfortable walking sneakers",
    ("travel", "outerwear"): "light zip-up jacket", ("travel", "footwear"): "slip-on sneakers",
}

# Weather gear: the phrase the weather service uses -> (what to buy, words that
# mean the user already owns one).
WEATHER_GEAR = {
    "umbrella or raincoat": ("compact umbrella or raincoat", ["umbrella", "raincoat"]),
    "sunglasses": ("UV-protection sunglasses", ["sunglass"]),
    "cap or hat": ("sun hat or cap", ["cap", "hat"]),
    "scarf": ("wool scarf", ["scarf", "stole", "muffler"]),
    "gloves": ("warm gloves", ["glove"]),
}

# Pieces that finish a look, by the category of an item in it:
# (words in the category, [(what to buy, words meaning it's owned)]).
COMPLEMENTS = [
    (("kurti", "kurta", "kameez", "anarkali", "sharara", "shalwar", "salwar"), [
        ("contrast dupatta", ["dupatta", "stole"]),
        ("embroidered juttis", ["jutti", "mojari", "kolhapuri"]),
        ("oxidised jhumkas", ["jhumka", "earring", "jewel"]),
    ]),
    (("saree", "lehenga"), [
        ("embellished clutch", ["clutch"]),
        ("statement earrings", ["earring", "jhumka", "jewel"]),
        ("bangles set", ["bangle", "jewel"]),
    ]),
    (("sherwani",), [
        ("embroidered mojaris", ["mojari", "jutti"]),
        ("brooch or safa", ["brooch", "safa"]),
    ]),
    (("shirt", "blazer", "trouser"), [
        ("minimal leather watch", ["watch"]),
        ("leather belt", ["belt"]),
        ("leather loafers", ["loafer"]),
    ]),
    (("t-shirt", "tshirt", "hoodie", "jeans", "jacket"), [
        ("clean white sneakers", ["sneaker"]),
        ("canvas tote or sling bag", ["bag", "tote", "sling"]),
        ("baseball cap", ["cap"]),
    ]),
    (("dress", "maxi", "skirt", "frock"), [
        ("strappy sandals", ["sandal"]),
        ("delicate earrings", ["earring", "jewel"]),
        ("sling bag", ["bag", "sling"]),
    ]),
]

# Colours that go with an item's main colour.
COLOR_PAIRS = {
    "navy": "tan", "blue": "white", "black": "gold", "white": "navy", "grey": "black",
    "red": "gold", "maroon": "gold", "pink": "silver", "beige": "brown", "cream": "brown",
    "brown": "cream", "green": "beige", "olive": "beige", "yellow": "white",
    "orange": "white", "purple": "silver", "teal": "gold", "mustard": "white",
}

COVERAGE_OCCASIONS = ["office", "casual", "party", "wedding"]


def _link(query: str) -> str:
    return f"https://www.google.com/search?q={quote_plus(query)}&tbm=shop"


def _article(word: str) -> str:
    return "an" if word[:1].lower() in "aeiou" else "a"


def _make(kind: str, slot: str | None, title: str, reason: str, query: str,
          rule: str, day: int | None = None) -> dict:
    out = {"kind": kind, "slot": slot, "title": title, "reason": reason,
           "suggestion": f"{title[:1].upper()}{title[1:]}: {reason}.",
           "rule": rule, "query": query, "search_link": _link(query)}
    if day:
        out["day"] = day
    return out


def _owns(items: list[dict], words: list[str]) -> bool:
    return any(w in prefs_mod.haystack(it) for it in items for w in words)


def _missing_slot(slot: str, occasion: str | None, cold: bool) -> dict:
    occ = occasion or "everyday"
    if slot == "outerwear" and cold:
        piece = OCCASION_PIECES.get((occ, slot), "warm jacket")
        return _make("missing", slot, piece, "the forecast is cold and you have nothing to layer with",
                     piece, "A neutral layer (black, navy, camel) goes over almost everything.")
    piece = OCCASION_PIECES.get((occ, slot), f"{occ} {SLOT_LABEL.get(slot, slot)}")
    return _make("missing", slot, piece,
                 f"your wardrobe has no {SLOT_LABEL.get(slot, slot)} at all",
                 piece, "Start with one neutral, versatile piece; it pairs with the most outfits.")


def _occasion_gaps(buckets: dict, occasion: str | None, slots: list[str],
                   day: int | None = None) -> list[dict]:
    """Slots that hold clothes, none of which suit the occasion."""
    out = []
    if not occasion:
        return out
    for slot in slots:
        owned = buckets.get(slot) or []
        if owned and not any(_matches_occasion(it, occasion) for it in owned):
            piece = OCCASION_PIECES.get((occasion, slot),
                                        f"{occasion} {SLOT_LABEL.get(slot, slot)}")
            label = SLOT_LABEL.get(slot, slot)
            out.append(_make(
                "occasion", slot, piece,
                f"none of your {SLOT_PLURAL.get(slot, slot + 's')} suit {_article(occasion)} {occasion}"
                + (f" (day {day})" if day else ""),
                piece, f"One good {occasion} {label} unlocks this occasion with what you already own.",
                day))
    return out


def _weather_gaps(items: list[dict], carry: list[str]) -> list[dict]:
    out = []
    for phrase in carry:
        gear = WEATHER_GEAR.get(phrase)
        if gear and not _owns(items, gear[1]):
            out.append(_make("weather", "accessory", gear[0],
                             f"the forecast calls for {phrase} and you don't have one",
                             gear[0], "Pick a compact one you can keep in your bag."))
    return out


def _complements(items: list[dict], chosen: list[dict]) -> list[dict]:
    """Pieces that finish the chosen outfit and aren't in the wardrobe yet."""
    out, seen = [], set()
    for it in chosen:
        category = str(it.get("category") or "").lower()
        colors = _colors(it)
        pair = next((COLOR_PAIRS[c] for c in colors if c in COLOR_PAIRS), None)
        for words, pieces in COMPLEMENTS:
            if not any(w in category for w in words):
                continue
            for piece, owned_words in pieces:
                if piece in seen or _owns(items, owned_words):
                    continue
                seen.add(piece)
                # No second colour on a piece that already names one ("white sneakers").
                names_color = any(w in COLOR_PAIRS or w == "white" for w in piece.split())
                pair = None if names_color else pair
                shade = f"{pair} " if pair else ""
                with_what = f"{colors[0]} {category}" if colors else category
                out.append(_make(
                    "complement", "accessory" if slot_of(piece) in (None, "accessory") else slot_of(piece),
                    f"{shade}{piece}".strip(),
                    f"it finishes the look with your {with_what}",
                    f"{shade}{piece}".strip(),
                    f"{pair.capitalize()} pairs well with {colors[0]}." if pair else
                    "Choose a neutral shade so it works with more outfits.",
                ))
                break                               # one piece per outfit item
    return out


def _coverage_gaps(buckets: dict, occasions: list[str]) -> list[dict]:
    """Occasions the wardrobe can't make a full outfit for (shopping questions)."""
    out = []
    for occ in occasions:
        fits = {s: [it for it in buckets.get(s, []) if _matches_occasion(it, occ)]
                for s in ("top", "bottom", "onepiece", "footwear")}
        has_body = fits["onepiece"] or (fits["top"] and fits["bottom"])
        if has_body and fits["footwear"]:
            continue
        need = [] if has_body else (["onepiece"] if occ == "wedding" else
                                    [s for s in ("top", "bottom") if not fits[s]])
        if not fits["footwear"]:
            need.append("footwear")
        for slot in need[:2]:
            piece = OCCASION_PIECES.get((occ, slot), f"{occ} {SLOT_LABEL.get(slot, slot)}")
            out.append(_make("coverage", slot, piece,
                             f"you have no {SLOT_LABEL.get(slot, slot)} for {_article(occ)} {occ} yet",
                             piece, f"Add this and you can put together a complete {occ} look."))
    return out


def _not_disliked(prefs: dict, suggestion: dict) -> bool:
    words = prefs.get("dislikes") or []
    return not prefs_mod.word_hits(words, f"{suggestion['title']} {suggestion['query']}".lower())


def _dedupe(suggestions: list[dict]) -> list[dict]:
    seen, out = set(), []
    for s in suggestions:
        key = s["title"].lower()
        if key not in seen:
            seen.add(key)
            out.append(s)
    return out


def gap(state: OutfitState) -> dict:
    occasion = state.get("occasion")
    prefs = state.get("prefs") or {}
    items = [it for it in (state.get("wardrobe_items") or [])
             if not prefs_mod.is_disliked(prefs, it)]
    buckets = group_by_slot(items)

    draft = state.get("draft_outfit") or {}
    cold = bool((draft.get("weather_signal") or {}).get("cold"))
    out: list[dict] = []

    if not draft:
        # A standalone "what should I buy?" question.
        for slot in CORE_SLOTS:
            if not buckets.get(slot):
                out.append(_missing_slot(slot, occasion, cold))
        if items:
            occasions = [occasion] if occasion else COVERAGE_OCCASIONS
            out += _coverage_gaps(buckets, occasions)
    else:
        # 1) Slots the outfit couldn't fill from the wardrobe.
        for slot in draft.get("missing_slots", []):
            if not buckets.get(slot):
                out.append(_missing_slot(slot, occasion, cold))
        # 2) Slots filled, but with nothing that suits the occasion.
        if draft.get("days"):
            plans = day_plans(state)
            for d in draft["days"]:
                # Name the day only when it has its own occasion in the plan.
                own = (plans.get(d["day"]) or {}).get("occasion")
                out += _occasion_gaps(buckets, d.get("occasion"),
                                      _body_slots(d.get("items")), d["day"] if own else None)
        else:
            out += _occasion_gaps(buckets, occasion, _body_slots(draft.get("items")))
        # 3) Weather gear the user doesn't own.
        out += _weather_gaps(items, draft.get("carry") or [])
        # 4) Pieces that finish the look.
        out += _complements(items, draft.get("items") or [])[:MAX_COMPLEMENTS]

    suggestions = [s for s in _dedupe(out) if _not_disliked(prefs, s)][:MAX_SUGGESTIONS]
    return {"missing_items": suggestions}


def _body_slots(chosen: list[dict] | None) -> list[str]:
    """The core slots an outfit is built from (onepiece replaces top + bottom)."""
    slots = {slot_of(it.get("category")) for it in chosen or []}
    return (["onepiece"] if "onepiece" in slots else ["top", "bottom"]) + ["footwear"]
