"""Node 5: gap — what the wardrobe is missing, and what to add.

Runs in two situations:
  - after a recommendation, to flag slots the outfit couldn't fill from what
    the user owns (e.g. no blazer for an office look);
  - as the whole answer to a "what should I buy?" question.

For each gap it produces a concrete suggestion: the slot, why it's needed, and
a shopping rule + a ready-made search link. (Links are generic searches, not an
affiliate feed — swap in a real catalogue later without touching this logic.)
"""
from urllib.parse import quote_plus

from .. import prefs as prefs_mod
from ..slots import group_by_slot, CORE_SLOTS
from ..state import OutfitState

# A readable thing to buy for each slot, given an occasion.
SLOT_LABEL = {
    "top": "a top", "bottom": "a bottom", "footwear": "footwear",
    "outerwear": "a jacket or blazer", "onepiece": "a dress/one-piece",
}


def _suggestion(slot: str, occasion: str | None, cold: bool) -> dict:
    label = SLOT_LABEL.get(slot, slot)
    occ = occasion or "everyday"
    article = "an" if occ[0] in "aeiou" else "a"
    if slot == "outerwear" and cold:
        reason = "the forecast is cold and you have nothing to layer with"
        query = f"{occ} jacket"
    else:
        reason = f"you have no {slot} that suits {article} {occ} look"
        query = f"{occ} {slot}"
    return {
        "slot": slot,
        "suggestion": f"Consider {label} — {reason}.",
        "rule": f"Pick one neutral, versatile {slot} first; it pairs with the most outfits.",
        "search_link": f"https://www.google.com/search?q={quote_plus(query)}&tbm=shop",
    }


def gap(state: OutfitState) -> dict:
    occasion = state.get("occasion")
    prefs = state.get("prefs") or {}
    items = [it for it in (state.get("wardrobe_items") or [])
             if not prefs_mod.is_disliked(prefs, it)]
    buckets = group_by_slot(items)

    draft = state.get("draft_outfit") or {}
    cold = bool((draft.get("weather_signal") or {}).get("cold"))

    gaps: list[str] = []

    # 1) Slots the just-built outfit couldn't fill from the wardrobe.
    for slot in draft.get("missing_slots", []):
        if not buckets.get(slot):
            gaps.append(slot)

    # 2) When this is a standalone "what to buy" question (no outfit built),
    #    report every empty core slot.
    if not draft:
        for slot in CORE_SLOTS:
            if not buckets.get(slot):
                gaps.append(slot)

    # De-dup, keep order.
    seen, ordered = set(), []
    for g in gaps:
        if g not in seen:
            seen.add(g)
            ordered.append(g)

    suggestions = [_suggestion(s, occasion, cold) for s in ordered]
    return {"missing_items": suggestions}
