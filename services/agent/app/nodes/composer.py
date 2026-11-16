"""Node 3: composer — build a candidate outfit from what the user owns.

Reads wardrobe_items + occasion + weather + prefs and picks one item per
slot (top, bottom, footwear, maybe outerwear — or a single onepiece), then
adds accessories the weather or occasion calls for. It returns a *draft*;
the critic decides if the draft is good enough.

For a multi-day trip it plans each day against that day's forecast, avoiding
items already used earlier in the trip (repeating one only when nothing else
fits the slot), and returns a day-by-day plan plus a packing list.

On a replay (critic said "try again"), `attempts` is higher, so the composer
rotates to different candidates instead of picking the same ones forever.
This rules version is swappable for an LLM composer later — same signature.
"""
from datetime import date as Date

from .. import prefs as prefs_mod
from ..slots import group_by_slot, slot_of, weather_types_of
from .planner import OCCASION_KEYWORDS
from ..state import OutfitState

SEARCH_BOOST_MAX = 5   # best search match gets +5; occasion match is worth +10
ONEPIECE_MARGIN = 3    # a dress/saree must beat both top and bottom by this much

LIGHT_COLORS = {"white", "cream", "beige", "ivory", "off-white", "pastel", "sky blue",
                "light blue", "light pink", "lavender", "mint", "peach", "yellow", "light"}

# Weather accessory phrase -> words that find it among the user's accessories.
WEATHER_ACCESSORIES = {
    "sunglasses": ["sunglass"],
    "cap or hat": ["cap", "hat"],
    "scarf": ["scarf", "stole", "muffler"],
    "gloves": ["glove"],
    "umbrella or raincoat": ["umbrella", "raincoat"],
}
# Occasion -> accessory words to add when the user owns one.
OCCASION_ACCESSORIES = {
    "wedding":  ["jewel", "earring", "necklace", "bangle", "clutch", "bag"],
    "festival": ["jewel", "earring", "necklace", "bangle", "bag"],
    "party":    ["jewel", "earring", "necklace", "clutch", "bag"],
    "date":     ["jewel", "earring", "bag"],
    "office":   ["bag", "watch"],
}
# Trip activities aren't occasion tags the vision service writes; these are
# the tags that suit them instead (vision tags trip-friendly items "trip").
OCCASION_TAGS = {
    "beach":       {"beach", "trip", "casual", "summer"},
    "hiking":      {"hiking", "trip", "sports", "gym"},
    "sightseeing": {"trip", "casual"},
    "travel":      {"trip", "casual"},
}
OCCASION_ACCESSORIES.update({
    "beach":       ["sunglass", "cap", "hat", "bag"],
    "sightseeing": ["sunglass", "bag"],
    "travel":      ["bag"],
})
# Outfits that are traditionally worn with a dupatta.
DUPATTA_WITH = {"kurti", "kameez", "anarkali", "shalwar", "sharara", "lehenga"}


# ---------------------------------------------------------------- weather ---

def _empty_signal() -> dict:
    return {"cold": False, "hot": False, "rain": False, "evening_layer": False,
            "temp": None, "temp_min": None,
            "types_prefer": set(), "types_avoid": set(),
            "materials_prefer": set(), "materials_avoid": set(),
            "colors_avoid": set(), "light_colors": False, "accessories": []}


def _day_signal(day: dict) -> dict:
    """One forecast day (weather service `days[i]`) -> what the outfit should do."""
    needs = day.get("needs") or {}
    sig = _empty_signal()
    sig["hot"] = day.get("label") == "hot"
    sig["cold"] = day.get("label") == "cold"
    sig["rain"] = bool(day.get("rainy"))
    sig["evening_layer"] = bool(needs.get("layer_for_evening"))
    if isinstance(day.get("max"), (int, float)):
        sig["temp"] = sig["temp_min"] = day["max"]
    sig["types_prefer"] = set(needs.get("types_prefer") or [])
    sig["types_avoid"] = set(needs.get("types_avoid") or [])
    sig["materials_prefer"] = set(needs.get("materials_prefer") or [])
    sig["materials_avoid"] = set(needs.get("materials_avoid") or [])
    sig["colors_avoid"] = set(needs.get("colors_avoid") or [])
    sig["light_colors"] = "light" in (needs.get("colors_prefer") or [])
    sig["accessories"] = list(needs.get("accessories") or [])
    return sig


def _weather_signal(weather: dict | None) -> dict:
    """The weather service's reply -> one signal for a single outfit.

    Reads the structured per-day fields (`days[i].label`, `.max`, `.rainy`,
    `.needs`) so the agent and the weather service agree on what "hot" and
    "cold" mean. Over several days a flag is set if *any* day needs it; a
    type/material is preferred if any day prefers it, but avoided only if
    *every* day avoids it (one outfit has to work on all of them).
    """
    days = [_day_signal(d) for d in (weather or {}).get("days") or []]
    if not days:
        return _empty_signal()
    sig = _empty_signal()
    for flag in ("cold", "hot", "rain", "evening_layer", "light_colors"):
        sig[flag] = any(d[flag] for d in days)
    temps = [d["temp"] for d in days if d["temp"] is not None]
    if temps:
        sig["temp"], sig["temp_min"] = max(temps), min(temps)
    for key in ("types_prefer", "materials_prefer", "colors_avoid"):
        sig[key] = set().union(*(d[key] for d in days))
    for key in ("types_avoid", "materials_avoid"):
        sig[key] = set.intersection(*(d[key] for d in days)) - sig[key.replace("avoid", "prefer")]
    sig["accessories"] = list(dict.fromkeys(a for d in days for a in d["accessories"]))
    return sig


# ---------------------------------------------------------------- scoring ---

def _matches_occasion(item: dict, occasion: str | None) -> bool:
    """Does the item's occasion tag fit? Uses the planner's synonyms, so an item
    tagged "festive" or "diwali" fits a "festival" request."""
    if not occasion:
        return True
    occ = item.get("occasion")
    tags = [str(o).lower() for o in occ] if isinstance(occ, list) else \
           [occ.lower()] if isinstance(occ, str) else []
    synonyms = set(OCCASION_KEYWORDS.get(occasion, [])) | OCCASION_TAGS.get(occasion, set())
    # The occasion itself may sit inside a longer tag ("office wear"); synonyms
    # must match a whole tag, so "work" doesn't match a "workout" item.
    return any(occasion in t or t in synonyms for t in tags)


def _search_boosts(scores: dict[str, float] | None,
                   search_text: str | None = None,
                   items: list[dict] | None = None) -> dict[str, int]:
    """How much each item matches what the user asked for, 0..SEARCH_BOOST_MAX.

    Two signals:
      - Field match: each asked-for word found in the item's tags (color,
        category, style, pattern, material, occasion, season) adds +3. Exact,
        works without CLIP, and handles plain colors ("red") well.
      - CLIP search scores (photo vs. words), scaled across this wardrobe —
        text-to-image cosines sit in a narrow band (~0.0-0.3), so only the
        ranking within the wardrobe means anything. Used only when some word
        isn't in any item's tags ("ethnic", "traditional"): when the tags
        already cover every word, CLIP's noisier ranking would only blur them.
    Per item, the stronger of the two wins.
    """
    words = [w for w in (search_text or "").split() if len(w) >= 3]
    hays = {it["id"]: prefs_mod.haystack(it) for it in items or [] if it.get("id")}
    field = {}
    for item_id, hay in hays.items():
        hits = sum(prefs_mod.word_hits([w], hay) for w in words)
        if hits:
            field[item_id] = min(SEARCH_BOOST_MAX, 3 * hits)
    tags_cover_all = bool(words) and all(
        any(prefs_mod.word_hits([w], hay) for hay in hays.values()) for w in words)

    boosts: dict[str, int] = {}
    if scores and not tags_cover_all:
        lo, hi = min(scores.values()), max(scores.values())
        if hi - lo >= 1e-6:
            boosts = {i: round(SEARCH_BOOST_MAX * (s - lo) / (hi - lo)) for i, s in scores.items()}
    for item_id, b in field.items():
        boosts[item_id] = max(boosts.get(item_id, 0), b)
    return boosts


def _colors(item: dict) -> list[str]:
    c = item.get("color")
    return [str(x).lower() for x in (c if isinstance(c, list) else [c] if c else [])]


def _weather_fit(item: dict, sig: dict) -> int:
    """Score from the weather service's advice: types, materials and colors."""
    s = 0
    types = weather_types_of(item.get("category"))
    if types & sig["types_prefer"]:
        s += 2
    if types & sig["types_avoid"]:
        s -= 4
    material = str(item.get("material") or "").lower()
    if material:
        if material in sig["materials_prefer"]:
            s += 1
        if material in sig["materials_avoid"]:
            s -= 2
    colors = _colors(item)
    if sig["colors_avoid"] and any(c in sig["colors_avoid"] for c in colors):
        s -= 1                                    # e.g. white on a rainy day
    if sig["light_colors"] and any(c in LIGHT_COLORS for c in colors):
        s += 1
    return s


def _score(item: dict, occasion: str | None, sig: dict, prefs: dict,
           boosts: dict[str, int] | None = None) -> int:
    """Higher = better fit. Used to order candidates for a slot."""
    s = (boosts or {}).get(item.get("id"), 0)
    if _matches_occasion(item, occasion):
        s += 10
    seasons = [str(x).lower() for x in (item.get("season") or [])]
    if sig["cold"] and ("winter" in seasons or "fall" in seasons):
        s += 3
    if sig["hot"] and "summer" in seasons:
        s += 3
    if sig["hot"] and "winter" in seasons:
        s -= 3
    s += _weather_fit(item, sig)
    if item.get("is_favorite"):
        s += 2
    if prefs_mod.is_liked(prefs, item):
        s += 4
    # Prefer less-worn items slightly, to vary suggestions over time.
    s -= min(int(item.get("wear_count") or 0), 3)
    return s


def _pick(candidates: list[dict], occasion, sig, prefs: dict, attempt: int,
          boosts: dict[str, int] | None = None, avoid_ids: set | None = None) -> dict | None:
    """Best candidate for a slot, rotated by `attempt` so replans differ.

    Candidates are tried in tiers, first non-empty tier wins:
      1. fresh and suits the weather
      2. a repeat that suits the weather   (re-wearing shoes beats sandals in the cold)
      3. fresh but the weather advises against it
      4. anything
    "Repeat" = worn within the user's avoid_repeat_days, or already used
    earlier on this trip (`avoid_ids`).
    """
    if not candidates:
        return None
    avoid_ids = avoid_ids or set()
    repeat = lambda it: prefs_mod.recently_worn(prefs, it) or it.get("id") in avoid_ids
    unsuited = lambda it: bool(weather_types_of(it.get("category")) & sig["types_avoid"])
    tiers = [
        [it for it in candidates if not repeat(it) and not unsuited(it)],
        [it for it in candidates if repeat(it) and not unsuited(it)],
        [it for it in candidates if not repeat(it)],
        candidates,
    ]
    pool = next(t for t in tiers if t)
    ordered = sorted(pool, key=lambda it: _score(it, occasion, sig, prefs, boosts), reverse=True)
    return ordered[attempt % len(ordered)]


def _family(item: dict | None) -> str | None:
    """'ethnic' or 'western' for tops and bottoms, so pairs match in style."""
    if not item:
        return None
    category = str(item.get("category") or "").lower()
    if "kurta" in weather_types_of(category) or any(
            w in category for w in ("shalwar", "salwar", "sharara", "churidar", "dhoti")):
        return "ethnic"
    return "western"


# ------------------------------------------------------------ composition ---

def _accessories(buckets, chosen, occasion, sig, prefs, attempt, boosts, avoid_ids):
    """Accessories the user owns that the weather / occasion / outfit call for,
    plus the weather's suggestions they don't own (to carry or keep in mind)."""
    owned = buckets.get("accessory", [])
    picked: list[dict] = []
    carry: list[str] = []

    def find(words):
        cands = [it for it in owned if it not in picked
                 and any(w in prefs_mod.haystack(it) for w in words)]
        return _pick(cands, occasion, sig, prefs, attempt, boosts, avoid_ids)

    for phrase in sig["accessories"]:
        hit = find(WEATHER_ACCESSORIES.get(phrase, [phrase]))
        if hit:
            picked.append(hit)
        else:
            carry.append(phrase)
    for word in OCCASION_ACCESSORIES.get(occasion or "", []):
        if not any(word in prefs_mod.haystack(p) for p in picked):
            hit = find([word])
            if hit:
                picked.append(hit)
                if word in ("bag", "clutch"):
                    break
    if any(str(it.get("category") or "").lower() in DUPATTA_WITH for it in chosen):
        hit = find(["dupatta", "stole"])
        if hit:
            picked.append(hit)
    return picked, carry


def _compose(buckets, occasion, sig, prefs, attempt, boosts, avoid_ids=None):
    """One outfit for one set of conditions -> (items, missing slots, used onepiece, carry)."""
    pick = lambda slot, cands=None: _pick(buckets.get(slot, []) if cands is None else cands,
                                          occasion, sig, prefs, attempt, boosts, avoid_ids)
    chosen: list[dict] = []
    missing: list[str] = []

    # A onepiece (dress/saree/anarkali) can stand in for top+bottom. Use it when
    # there's no full top+bottom pair, or when it clearly fits better than both
    # pieces — by an occasion or search match, not by tag noise. Otherwise the
    # separates win.
    onepiece, top = pick("onepiece"), pick("top")
    # The bottom matches the top's style (kurti + sharara, t-shirt + jeans) when
    # the wardrobe has one — even if that means a repeat — else anything goes.
    bottoms = buckets.get("bottom", [])
    matching = [b for b in bottoms if _family(b) == _family(top)]
    bottom = pick("bottom", matching or bottoms)
    score = lambda it: _score(it, occasion, sig, prefs, boosts)
    used_onepiece = bool(onepiece) and (
        not (top and bottom)
        or score(onepiece) >= max(score(top), score(bottom)) + ONEPIECE_MARGIN
    )
    slots = [("onepiece", onepiece)] if used_onepiece else [("top", top), ("bottom", bottom)]
    slots.append(("footwear", pick("footwear")))
    # A layer is part of the outfit only when it's actually cold.
    if sig["cold"]:
        slots.append(("outerwear", pick("outerwear")))
    for slot, it in slots:
        if it:
            chosen.append(it)
        else:
            missing.append(slot)

    extras, carry = _accessories(buckets, chosen, occasion, sig, prefs, attempt, boosts, avoid_ids)
    return chosen + extras, missing, used_onepiece, carry


def _rationale(occasion: str | None, sig: dict) -> str:
    bits = []
    if occasion:
        article = "an" if occasion[0] in "aeiou" else "a"
        bits.append(f"for {article} {occasion} occasion")
    if sig["temp"] is not None:
        if sig["temp_min"] is not None and sig["temp_min"] != sig["temp"]:
            bits.append(f"highs {sig['temp_min']}–{sig['temp']}°C")
        else:
            bits.append(f"high of {sig['temp']}°C")
    if sig["hot"]:
        bits.append("hot, so keep it light")
    if sig["cold"]:
        bits.append("cold, so a layer helps")
    elif sig["evening_layer"]:
        bits.append("carry a light layer for the evening")
    if sig["rain"]:
        bits.append("rain likely, so skip white and pick quick-drying fabrics")
    return "; ".join(bits) or "general recommendation"


def _trip_days(state: OutfitState) -> list[dict]:
    """The days to plan: the forecast's days, then blank days for any the
    forecast doesn't reach (weather down, or beyond its 16 days)."""
    days = list((state.get("weather") or {}).get("days") or [])
    count = int((state.get("dates") or {}).get("count") or 0)
    count = max(count, max((d["day"] for d in state.get("itinerary") or []), default=0))
    return days + [{} for _ in range(max(0, count - len(days)))] if (days or count) else []


def day_plans(state: OutfitState) -> dict[int, dict]:
    """{day number: itinerary entry} for the trip's per-day plans."""
    return {int(d["day"]): d for d in state.get("itinerary") or [] if d.get("day")}


def composer(state: OutfitState) -> dict:
    occasion = state.get("occasion")
    prefs = state.get("prefs") or {}
    attempt = int(state.get("attempts") or 0)

    # Drop anything the user has told us they dislike (words or thumbs-down).
    items = [it for it in (state.get("wardrobe_items") or [])
             if not prefs_mod.is_disliked(prefs, it)]
    boosts = _search_boosts(state.get("search_scores"), state.get("search_text"), items)
    buckets = group_by_slot(items)
    overall = _weather_signal(state.get("weather"))

    days = _trip_days(state) if state.get("intent") == "trip" else []
    plans = day_plans(state)
    if len(days) < 2:
        occasion = (plans.get(1) or {}).get("occasion") or occasion
        chosen, missing, used_onepiece, carry = _compose(
            buckets, occasion, overall, prefs, attempt, boosts)
        return {"draft_outfit": {
            "items": chosen,
            "used_onepiece": used_onepiece,
            "missing_slots": missing,
            "carry": carry,
            "rationale": _rationale(occasion, overall),
            "weather_signal": overall,
        }}

    # --- multi-day trip: one outfit per day, each against its own forecast ---
    plan, packing, missing_all, carry_all = [], {}, [], []
    used_ids: set = set()
    for i, day in enumerate(days):
        sig = _day_signal(day) if day else _empty_signal()
        plan_i = plans.get(i + 1) or {}
        day_occasion = plan_i.get("occasion") or occasion
        chosen, missing, _, carry = _compose(buckets, day_occasion, sig, prefs, attempt,
                                             boosts, avoid_ids=used_ids)
        # Clothes shouldn't repeat across the trip if avoidable; accessories may.
        used_ids |= {it["id"] for it in chosen
                     if it.get("id") and slot_of(it.get("category")) != "accessory"}
        for it in chosen:
            packing.setdefault(it.get("id") or id(it), it)
        missing_all += [m for m in missing if m not in missing_all]
        carry_all += [c for c in carry if c not in carry_all]
        plan.append({
            "day": i + 1,
            "date": day.get("date"),
            "label": day.get("label"),
            "max": day.get("max"),
            "min": day.get("min"),
            "rainy": day.get("rainy"),
            "occasion": day_occasion,
            "activity": plan_i.get("activity"),
            "items": chosen,
            "missing_slots": missing,
            "rationale": _rationale(plan_i.get("occasion"), sig),
        })
    trip = (state.get("weather") or {}).get("trip") or {}
    for a in trip.get("accessories") or []:
        if a not in carry_all and not any(
                w in prefs_mod.haystack(it) for it in packing.values()
                for w in WEATHER_ACCESSORIES.get(a, [a])):
            carry_all.append(a)
    if trip.get("needs_evening_layer") and not overall["cold"]:
        carry_all.append("a light layer for the evenings")
    return {"draft_outfit": {
        "items": list(packing.values()),        # packing list: each item once
        "days": plan,
        "used_onepiece": any(slot_of(it.get("category")) == "onepiece" for it in packing.values()),
        "missing_slots": missing_all,
        "carry": carry_all,
        "rationale": _rationale(occasion, overall),
        "weather_signal": overall,
    }}


def format_day(d: dict) -> str:
    """'Sat 14 Nov' from an ISO date string (or 'Day N' if missing)."""
    try:
        return Date.fromisoformat(d["date"]).strftime("%a %d %b")
    except (KeyError, TypeError, ValueError):
        return f"Day {d.get('day')}"
