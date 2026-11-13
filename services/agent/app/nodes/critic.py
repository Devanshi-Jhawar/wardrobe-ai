"""Node 4: critic — is the draft outfit actually good?

Checks the composer's draft for two things:
  1. Completeness — are the core slots (top+bottom, or a onepiece, + footwear)
     filled? A slot the wardrobe simply can't fill isn't the composer's fault,
     so it's handed to the gap node instead of looping forever.
  2. Occasion fit — if an occasion was asked for, does at least one chosen
     item actually suit it?

If there's a *fixable* problem it fails the draft → the graph loops back to the
composer to try again. It never loops more than MAX_ATTEMPTS times: once the cap
is hit it passes the best effort through with a note. This is the conditional
"replan" edge we designed.
"""
from .. import config
from ..slots import group_by_slot, CORE_SLOTS
from ..nodes.composer import _matches_occasion
from ..state import OutfitState


def critic(state: OutfitState) -> dict:
    attempts = int(state.get("attempts") or 0) + 1
    draft = state.get("draft_outfit") or {}
    occasion = state.get("occasion")
    chosen = draft.get("items", [])
    missing = draft.get("missing_slots", [])

    # Which missing core slots could a retry even fix? Only ones the wardrobe
    # actually has items for. (Outerwear is a "nice to have", never a hard fail.)
    buckets = group_by_slot(state.get("wardrobe_items") or [])
    fixable_missing = [s for s in missing
                       if s in CORE_SLOTS and buckets.get(s)]
    unfixable_missing = [s for s in missing
                         if s in CORE_SLOTS and not buckets.get(s)]

    # Occasion fit.
    occasion_ok = True
    if occasion and chosen:
        occasion_ok = any(_matches_occasion(it, occasion) for it in chosen)
    has_alternatives = bool(occasion) and any(
        _matches_occasion(it, occasion)
        for slot in CORE_SLOTS for it in buckets.get(slot, [])
    )

    notes = []
    good = True
    if fixable_missing:
        good = False
        notes.append(f"missing {', '.join(fixable_missing)} but wardrobe has options")
    if not occasion_ok and has_alternatives:
        good = False
        notes.append(f"nothing chosen really fits a {occasion} occasion")
    if unfixable_missing:
        notes.append(f"wardrobe has no {', '.join(unfixable_missing)} (gap)")

    # Give up retrying once we've hit the cap — pass the best effort through.
    if not good and attempts >= config.MAX_ATTEMPTS:
        good = True
        notes.append(f"accepted after {attempts} attempts (best effort)")

    return {
        "attempts": attempts,
        "critic_passed": good,
        "critic_notes": "; ".join(notes) or "looks good",
    }
