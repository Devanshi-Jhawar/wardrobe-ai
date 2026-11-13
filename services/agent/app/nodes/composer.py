"""Node 3: composer — build a candidate outfit from what the user owns.

Reads wardrobe_items + occasion + weather + prefs and picks one item per
slot (top, bottom, footwear, maybe outerwear — or a single onepiece). It
returns a *draft*; the critic decides if the draft is good enough.

On a replay (critic said "try again"), `attempts` is higher, so the composer
rotates to different candidates instead of picking the same ones forever.
This rules version is swappable for an LLM composer later — same signature.
"""
from .. import prefs as prefs_mod
from ..slots import group_by_slot
from .planner import OCCASION_KEYWORDS
from ..state import OutfitState


def _weather_signal(weather: dict | None) -> dict:
    """Boil the weather service's reply down to hot / cold / rain flags.

    Reads the structured per-day fields the weather service returns
    (`days[i].label`, `.max`, `.rainy`, `.needs.layer_for_evening`) so the
    agent and the weather service agree on what "hot" and "cold" mean.
    Over several days (a trip) a flag is set if *any* day needs it.
    """
    sig = {"cold": False, "hot": False, "rain": False, "evening_layer": False,
           "temp": None, "temp_min": None}
    days = (weather or {}).get("days") or []
    if not days:
        return sig
    labels = [d.get("label") for d in days]
    highs = [d["max"] for d in days if isinstance(d.get("max"), (int, float))]
    sig["hot"] = "hot" in labels
    sig["cold"] = "cold" in labels
    sig["rain"] = any(d.get("rainy") for d in days)
    sig["evening_layer"] = any((d.get("needs") or {}).get("layer_for_evening") for d in days)
    if highs:
        sig["temp"] = max(highs)          # warmest day's high
        sig["temp_min"] = min(highs)      # coolest day's high (== temp for one day)
    return sig


def _matches_occasion(item: dict, occasion: str | None) -> bool:
    """Does the item's occasion tag fit? Uses the planner's synonyms, so an item
    tagged "festive" or "diwali" fits a "festival" request."""
    if not occasion:
        return True
    occ = item.get("occasion")
    tags = [str(o).lower() for o in occ] if isinstance(occ, list) else \
           [occ.lower()] if isinstance(occ, str) else []
    synonyms = set(OCCASION_KEYWORDS.get(occasion, []))
    # The occasion itself may sit inside a longer tag ("office wear"); synonyms
    # must match a whole tag, so "work" doesn't match a "workout" item.
    return any(occasion in t or t in synonyms for t in tags)


SEARCH_BOOST_MAX = 5   # best search match gets +5; occasion match is worth +10
ONEPIECE_MARGIN = 3    # a dress/saree must beat both top and bottom by this much


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
    if item.get("is_favorite"):
        s += 2
    if prefs_mod.is_liked(prefs, item):
        s += 4
    # Prefer less-worn items slightly, to vary suggestions over time.
    s -= min(int(item.get("wear_count") or 0), 3)
    return s


def _pick(candidates: list[dict], occasion, sig, prefs: dict, attempt: int,
          boosts: dict[str, int] | None = None) -> dict | None:
    """Best candidate for a slot, rotated by `attempt` so replans differ.

    Items worn within the user's avoid_repeat_days are skipped — unless that
    would leave the slot empty, in which case a repeat beats nothing.
    """
    if not candidates:
        return None
    fresh = [it for it in candidates if not prefs_mod.recently_worn(prefs, it)]
    pool = fresh or candidates
    ordered = sorted(pool, key=lambda it: _score(it, occasion, sig, prefs, boosts), reverse=True)
    return ordered[attempt % len(ordered)]


def composer(state: OutfitState) -> dict:
    occasion = state.get("occasion")
    sig = _weather_signal(state.get("weather"))
    prefs = state.get("prefs") or {}
    attempt = int(state.get("attempts") or 0)

    # Drop anything the user has told us they dislike (words or thumbs-down).
    items = [it for it in (state.get("wardrobe_items") or [])
             if not prefs_mod.is_disliked(prefs, it)]
    boosts = _search_boosts(state.get("search_scores"), state.get("search_text"), items)
    buckets = group_by_slot(items)

    chosen: list[dict] = []
    missing: list[str] = []
    used_onepiece = False

    # A onepiece (dress/kurta set) can stand in for top+bottom.
    onepiece = _pick(buckets.get("onepiece", []), occasion, sig, prefs, attempt, boosts)
    bottom = _pick(buckets.get("bottom", []), occasion, sig, prefs, attempt, boosts)
    top = _pick(buckets.get("top", []), occasion, sig, prefs, attempt, boosts)

    # Use the onepiece when there's no full top+bottom pair, or when it clearly
    # fits better than both pieces — by an occasion or search match, not by
    # tag noise (e.g. "I want to wear my saree", or a festival).
    # Otherwise the separates win, as before.
    score = lambda it: _score(it, occasion, sig, prefs, boosts)
    onepiece_wins = bool(onepiece) and (
        not (top and bottom)
        or score(onepiece) >= max(score(top), score(bottom)) + ONEPIECE_MARGIN
    )
    if onepiece_wins:
        chosen.append(onepiece)
        used_onepiece = True
    else:
        if top:
            chosen.append(top)
        else:
            missing.append("top")
        if bottom:
            chosen.append(bottom)
        else:
            missing.append("bottom")

    footwear = _pick(buckets.get("footwear", []), occasion, sig, prefs, attempt, boosts)
    if footwear:
        chosen.append(footwear)
    else:
        missing.append("footwear")

    # A layer is part of the outfit only when it's actually cold.
    if sig["cold"]:
        outer = _pick(buckets.get("outerwear", []), occasion, sig, prefs, attempt, boosts)
        if outer:
            chosen.append(outer)
        else:
            missing.append("outerwear")

    rationale_bits = []
    if occasion:
        article = "an" if occasion[0] in "aeiou" else "a"
        rationale_bits.append(f"for {article} {occasion} occasion")
    if sig["temp"] is not None:
        if sig["temp_min"] is not None and sig["temp_min"] != sig["temp"]:
            rationale_bits.append(f"highs {sig['temp_min']}–{sig['temp']}°C")
        else:
            rationale_bits.append(f"high of {sig['temp']}°C")
    if sig["hot"]:
        rationale_bits.append("hot, so keep it light")
    if sig["cold"]:
        rationale_bits.append("cold, so a layer helps")
    elif sig["evening_layer"]:
        rationale_bits.append("carry a light layer for the evening")
    if sig["rain"]:
        rationale_bits.append("rain likely")

    draft = {
        "items": chosen,
        "used_onepiece": used_onepiece,
        "missing_slots": missing,
        "rationale": "; ".join(rationale_bits) or "general recommendation",
        "weather_signal": sig,
    }
    return {"draft_outfit": draft}
