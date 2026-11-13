"""Node 3: composer — build a candidate outfit from what the user owns.

Reads wardrobe_items + occasion + weather + prefs and picks one item per
slot (top, bottom, footwear, maybe outerwear — or a single onepiece). It
returns a *draft*; the critic decides if the draft is good enough.

On a replay (critic said "try again"), `attempts` is higher, so the composer
rotates to different candidates instead of picking the same ones forever.
This rules version is swappable for an LLM composer later — same signature.
"""
import json

from .. import memory_store
from ..slots import group_by_slot, CORE_SLOTS
from ..state import OutfitState


def _weather_signal(weather: dict | None) -> dict:
    """Boil the weather payload down to cold / hot / rain flags + a temp."""
    sig = {"cold": False, "hot": False, "rain": False, "temp": None}
    if not weather:
        return sig
    blob = json.dumps(weather).lower()
    # Pull any temperature-looking number to classify cold/hot.
    temp = None
    for key in ("temp", "temperature", "temp_max", "max_temp", "feels_like", "apparent"):
        if key in weather and isinstance(weather[key], (int, float)):
            temp = weather[key]
            break
    sig["temp"] = temp
    if temp is not None:
        sig["cold"] = temp < 16
        sig["hot"] = temp > 30
    # Keyword backup (the weather service emits rule-based needs text).
    if any(w in blob for w in ("cold", "chilly", "jacket", "layer", "warm clothes", "winter")):
        sig["cold"] = True
    if any(w in blob for w in ("rain", "shower", "drizzle", "umbrella", "wet")):
        sig["rain"] = True
    if any(w in blob for w in ("hot", "heat", "sunny and warm", "summer")):
        sig["hot"] = True
    return sig


def _matches_occasion(item: dict, occasion: str | None) -> bool:
    if not occasion:
        return True
    occ = item.get("occasion")
    if isinstance(occ, list):
        return any(occasion in str(o).lower() for o in occ)
    if isinstance(occ, str):
        return occasion in occ.lower()
    return False


def _score(item: dict, occasion: str | None, sig: dict) -> int:
    """Higher = better fit. Used to order candidates for a slot."""
    s = 0
    if _matches_occasion(item, occasion):
        s += 10
    seasons = [str(x).lower() for x in (item.get("season") or [])]
    if sig["cold"] and ("winter" in seasons or "fall" in seasons):
        s += 3
    if sig["hot"] and "summer" in seasons:
        s += 3
    if item.get("is_favorite"):
        s += 2
    # Prefer less-worn items slightly, to vary suggestions over time.
    s -= min(int(item.get("wear_count") or 0), 3)
    return s


def _pick(candidates: list[dict], occasion, sig, attempt: int) -> dict | None:
    """Best candidate for a slot, rotated by `attempt` so replans differ."""
    if not candidates:
        return None
    ordered = sorted(candidates, key=lambda it: _score(it, occasion, sig), reverse=True)
    return ordered[attempt % len(ordered)]


def composer(state: OutfitState) -> dict:
    occasion = state.get("occasion")
    sig = _weather_signal(state.get("weather"))
    prefs = state.get("prefs") or {}
    attempt = int(state.get("attempts") or 0)

    # Drop anything the user has told us they dislike.
    items = [it for it in (state.get("wardrobe_items") or [])
             if not memory_store.is_disliked(prefs, it)]
    buckets = group_by_slot(items)

    chosen: list[dict] = []
    missing: list[str] = []
    used_onepiece = False

    # A onepiece (dress/kurta set) can stand in for top+bottom.
    onepiece = _pick(buckets.get("onepiece", []), occasion, sig, attempt)
    bottom = _pick(buckets.get("bottom", []), occasion, sig, attempt)
    top = _pick(buckets.get("top", []), occasion, sig, attempt)

    if onepiece and (not (top and bottom)):
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

    footwear = _pick(buckets.get("footwear", []), occasion, sig, attempt)
    if footwear:
        chosen.append(footwear)
    else:
        missing.append("footwear")

    # Add a layer when it's cold and we have one.
    if sig["cold"]:
        outer = _pick(buckets.get("outerwear", []), occasion, sig, attempt)
        if outer:
            chosen.append(outer)
        else:
            missing.append("outerwear")

    rationale_bits = []
    if occasion:
        rationale_bits.append(f"for a {occasion} occasion")
    if sig["temp"] is not None:
        rationale_bits.append(f"~{sig['temp']}°")
    if sig["cold"]:
        rationale_bits.append("cold, so a layer helps")
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
