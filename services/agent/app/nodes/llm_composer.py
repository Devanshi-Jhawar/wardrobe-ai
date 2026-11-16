"""The LLM stylist: picks the outfit from the user's own wardrobe.

The rules composer always runs first. Its draft is the fallback and the source
for anything the LLM leaves out. The LLM then sees the wardrobe (with short
ids, i1, i2, ...), the weather, the occasion and the user's taste, and picks
items for each day with a sentence on why. Its choice goes through guardrails
before it's used:

  - only ids that exist in the wardrobe (disliked items were already removed)
  - one item per clothing slot, a onepiece never together with a top/bottom
  - nothing that breaks the occasion's dress code (slippers to a wedding)
    while the wardrobe has an alternative
  - at most MAX_ACCESSORIES accessories
  - core slots the LLM forgot (no footwear) are filled from the rules' draft

Any failure (no key, timeout, bad JSON, nothing valid) returns None and the
rules' draft is used unchanged.
"""
from .. import llm
from .. import prefs as prefs_mod
from ..slots import slot_of
from .composer import _breaks_dress_code, format_day

MAX_ACCESSORIES = 4
CLOTHING_SLOTS = ("top", "bottom", "onepiece", "footwear", "outerwear")

SYSTEM = """You are a personal stylist choosing outfits from the user's own wardrobe. Return JSON only.

Rules:
- Use only item ids from the wardrobe list. Never invent items.
- Per day: either a top and a bottom, or one onepiece (dress, saree, lehenga, anarkali, jumpsuit); plus footwear. Add outerwear only when it's cold, or a blazer for formal work days. Add accessories that suit the occasion (at most 4).
- Dress for the occasion the way a well-dressed person in India would: festive or ethnic wear for weddings and festivals, smart or formal for office, nothing too casual (slippers, track pants) for dressed-up events.
- Respect the weather: light breathable pieces when hot, layers when cold, avoid suede and white in rain.
- Prefer items the user likes or marked favourite. Avoid items marked "worn recently" unless there is no good alternative.
- Colours should go together. A kurti, kameez, anarkali or sharara usually takes a dupatta if one is available.
- On a multi-day trip, don't repeat clothes across days when there's an alternative; accessories and footwear may repeat.
- note: one or two short sentences to the user on why this works (occasion, weather, colours). Plain text, no emoji.

Reply: {"days": [{"day": 1, "items": ["i3", "i7"], "note": "..."}]}"""


def _describe(item: dict, short: str, prefs: dict) -> str:
    def join(v):
        return ", ".join(str(x) for x in v) if isinstance(v, list) else str(v or "")
    bits = [f"{short}: {item.get('category') or 'item'} ({slot_of(item.get('category')) or 'other'})"]
    for label, key in (("colours", "color"), ("style", "style"), ("pattern", "pattern"),
                       ("material", "material"), ("occasions", "occasion"), ("seasons", "season")):
        v = join(item.get(key))
        if v:
            bits.append(f"{label}: {v}")
    flags = [f for f, on in (("favourite", item.get("is_favorite")),
                             ("liked", prefs_mod.is_liked(prefs, item)),
                             ("worn recently", prefs_mod.recently_worn(prefs, item))) if on]
    if flags:
        bits.append("[" + ", ".join(flags) + "]")
    return "; ".join(bits)


def _day_line(n: int, day: dict, occasion: str | None, activity: str | None) -> str:
    parts = [f"Day {n}"]
    if day.get("date"):
        try:
            parts.append(format_day({"date": day["date"]}))
        except Exception:
            parts.append(str(day["date"]))
    if day.get("max") is not None:
        parts.append(f"high {day['max']}°C, low {day.get('min')}°C, {day.get('label') or ''}".strip(", "))
    if day.get("rainy"):
        parts.append("rain likely")
    parts.append(f"occasion: {occasion or 'everyday'}")
    if activity:
        parts.append(f"plan: {activity}")
    return "; ".join(parts)


def build_prompt(state: dict, items: list[dict], days: list[dict], plans: dict, occasion: str | None,
                 prefs: dict) -> tuple[str, dict[str, dict]]:
    """The user message and the short-id -> item map."""
    by_short = {f"i{i + 1}": it for i, it in enumerate(items)}
    place = (state.get("weather") or {}).get("place")
    lines = [f"Request: {state.get('query') or ''}"]
    if place:
        lines.append(f"Place: {place}")
    if not state.get("weather"):
        lines.append("Weather: unknown")
    lines.append("Days:")
    for i, day in enumerate(days or [{}]):
        plan = plans.get(i + 1) or {}
        lines.append("- " + _day_line(i + 1, day, plan.get("occasion") or occasion, plan.get("activity")))
    if prefs.get("likes"):
        lines.append("User likes: " + ", ".join(prefs["likes"]))
    if prefs.get("dislikes"):
        lines.append("User dislikes (already removed from the list): " + ", ".join(prefs["dislikes"]))
    if state.get("search_text"):
        lines.append(f"User asked for: {state['search_text']}")
    lines.append("Wardrobe:")
    lines += [_describe(it, s, prefs) for s, it in by_short.items()]
    return "\n".join(lines), by_short


def validate(ids, by_short: dict, occasion: str | None, rules_items: list[dict],
             buckets: dict) -> list[dict]:
    """Apply the guardrails to one day's pick; fill forgotten core slots from the rules."""
    picked: list[dict] = []
    taken: dict[str, dict] = {}
    extras: list[dict] = []
    for raw in ids if isinstance(ids, list) else []:
        it = by_short.get(str(raw).strip())
        if not it or it in picked:
            continue
        slot = slot_of(it.get("category")) or "accessory"
        # Dress code: skip a "never" piece while the slot has a proper option.
        if _breaks_dress_code(it, occasion) and any(
                not _breaks_dress_code(o, occasion) for o in buckets.get(slot, [])):
            continue
        if slot in CLOTHING_SLOTS:
            if slot in taken:
                continue
            if slot == "onepiece" and ("top" in taken or "bottom" in taken):
                continue
            if slot in ("top", "bottom") and "onepiece" in taken:
                continue
            taken[slot] = it
        else:
            if len(extras) >= MAX_ACCESSORIES:
                continue
            extras.append(it)
        picked.append(it)

    if not taken:
        return []   # nothing wearable: not a usable answer
    # Fill core slots the LLM left out from the rules' draft for this day.
    rules_by_slot = {slot_of(it.get("category")): it for it in rules_items}
    need = ["footwear"] + ([] if "onepiece" in taken else ["top", "bottom"])
    for slot in need:
        if slot not in taken and rules_by_slot.get(slot) and rules_by_slot[slot] not in picked:
            taken[slot] = rules_by_slot[slot]
    return [taken[s] for s in CLOTHING_SLOTS if s in taken] + extras


def compose(state: dict, items: list[dict], buckets: dict, days: list[dict], plans: dict,
            occasion: str | None, prefs: dict, rules_days: list[list[dict]]) -> list[dict] | None:
    """[{"items": [...], "note": str}] per day, or None to keep the rules' draft."""
    if not llm.enabled() or not items:
        return None
    user, by_short = build_prompt(state, items, days, plans, occasion, prefs)
    n_days = max(1, len(days))
    data = llm.chat_json(SYSTEM, user, max_tokens=250 + 150 * n_days)
    if not isinstance(data, dict) or not isinstance(data.get("days"), list):
        return None
    replies = {}
    for d in data["days"]:
        if isinstance(d, dict):
            try:
                replies[int(d.get("day") or 1)] = d
            except (TypeError, ValueError):
                continue
    out = []
    for i in range(n_days):
        reply = replies.get(i + 1) or {}
        day_occ = (plans.get(i + 1) or {}).get("occasion") or occasion
        chosen = validate(reply.get("items"), by_short, day_occ, rules_days[i], buckets)
        if not chosen:
            return None   # one bad day: keep the whole rules plan, it's consistent
        note = reply.get("note")
        out.append({"items": chosen,
                    "note": note.strip()[:400] if isinstance(note, str) and note.strip() else None})
    return out
