"""Node 6: answer — turn the filled-in State into the final reply.

The last node. It reads whatever the earlier nodes produced and shapes a
single `final_answer` dict: a human-readable `message` plus structured fields
the API can return as JSON. It decides nothing new — it just presents.
"""
from ..state import OutfitState
from .composer import format_day


def _describe(item: dict) -> str:
    """A short human label for a wardrobe item."""
    color = item.get("color")
    if isinstance(color, list):
        color = color[0] if color else ""
    parts = [str(color or "").strip(), str(item.get("category") or "item").strip()]
    return " ".join(p for p in parts if p) or "item"


def answer(state: OutfitState) -> dict:
    intent = state.get("intent", "recommend")

    # --- saved a preference ---
    if intent == "save_preference":
        thing = state.get("preference")
        kind = state.get("preference_kind") or "dislike"
        verb = "like" if kind == "like" else "don't like"
        if not thing:
            msg = ("I couldn't tell what you meant — try \"I don't like frocks\" "
                   "or \"I love blue\".")
            return {"final_answer": {"type": "preference_not_saved", "message": msg,
                                     "kind": kind, "remembered": []}}
        if not state.get("memory_saved"):
            msg = (f"I understood you {verb} {thing}, but I couldn't save it — "
                   "the memory service isn't reachable right now.")
            return {"final_answer": {"type": "preference_not_saved", "message": msg,
                                     "kind": kind, "remembered": []}}
        if kind == "like":
            msg = f"Noted — you like {thing}. I'll pick those first when they fit."
        else:
            msg = f"Got it — I'll stop suggesting {thing}. I'll remember that from now on."
        return {"final_answer": {"type": "preference_saved",
                                 "message": msg,
                                 "kind": kind,
                                 "remembered": state.get("preferences") or []}}

    # --- pure shopping / gap question ---
    if intent == "gap":
        gaps = state.get("missing_items") or []
        if gaps:
            lines = [g["suggestion"] for g in gaps]
            msg = "Here's what would round out your wardrobe:\n- " + "\n- ".join(lines)
        else:
            msg = "Your wardrobe already covers the basics — nothing essential missing."
        return {"final_answer": {"type": "gap",
                                 "message": msg,
                                 "suggestions": gaps}}

    draft = state.get("draft_outfit") or {}
    gaps = state.get("missing_items") or []
    if draft.get("days"):
        return _trip_answer(state, draft, gaps)

    # --- a single recommendation ---
    chosen = draft.get("items", [])

    if chosen:
        outfit_line = ", ".join(_describe(it) for it in chosen)
        msg = f"Here's an outfit: {outfit_line}."
        if draft.get("rationale"):
            msg += f" ({draft['rationale']})"
    else:
        msg = "I couldn't put a full outfit together from your current wardrobe."

    carry = draft.get("carry") or []
    if carry:
        msg += f"\nAlso carry: {', '.join(carry)}."
    if gaps:
        msg += "\n\nTo complete the look, consider:\n- " + \
               "\n- ".join(g["suggestion"] for g in gaps)

    return {"final_answer": {
        "type": "recommendation",
        "message": msg,
        "outfit": [_item_out(it) for it in chosen],
        "item_ids": [it.get("id") for it in chosen if it.get("id")],
        "carry": carry,
        "rationale": draft.get("rationale"),
        "critic_notes": state.get("critic_notes"),
        "attempts": state.get("attempts", 0),
        "suggestions": gaps,
    }}


def _item_out(it: dict) -> dict:
    return {"id": it.get("id"), "category": it.get("category"),
            "color": it.get("color"), "style": it.get("style"),
            "image_url": it.get("image_url")}


def _trip_answer(state: OutfitState, draft: dict, gaps: list[dict]) -> dict:
    """A day-by-day plan, a packing list (each item once) and what to carry."""
    days = draft["days"]
    where = f" in {state['city']}" if state.get("city") else ""
    lines = [f"Here's your {len(days)}-day plan{where}:"]
    for d in days:
        weather = []
        if d.get("max") is not None:
            weather.append(f"{d['max']}°C")
        if d.get("label"):
            weather.append(d["label"])
        if d.get("rainy"):
            weather.append("rain")
        head = f"Day {d['day']} · {format_day(d)}" + (f" ({', '.join(weather)})" if weather else "")
        plan = d.get("activity") or d.get("occasion")
        if plan and plan != state.get("occasion"):
            head += f" for {plan}"
        outfit = ", ".join(_describe(it) for it in d["items"]) or "nothing suitable in your wardrobe"
        lines.append(f"- {head}: {outfit}")
    packing = draft.get("items") or []
    if packing:
        lines.append(f"\nPack ({len(packing)} items): " + ", ".join(_describe(it) for it in packing) + ".")
    if draft.get("carry"):
        lines.append(f"Also carry: {', '.join(draft['carry'])}.")
    if gaps:
        lines.append("\nTo complete the trip, consider:\n- " + "\n- ".join(g["suggestion"] for g in gaps))
    return {"final_answer": {
        "type": "trip_plan",
        "message": "\n".join(lines),
        "days": [{"day": d["day"], "date": d.get("date"), "label": d.get("label"),
                  "max": d.get("max"), "min": d.get("min"), "rainy": d.get("rainy"),
                  "occasion": d.get("occasion"), "activity": d.get("activity"),
                  "outfit": [_item_out(it) for it in d["items"]],
                  "item_ids": [it.get("id") for it in d["items"] if it.get("id")],
                  "rationale": d.get("rationale")} for d in days],
        "packing_list": [_item_out(it) for it in packing],
        "carry": draft.get("carry") or [],
        "rationale": draft.get("rationale"),
        "critic_notes": state.get("critic_notes"),
        "attempts": state.get("attempts", 0),
        "suggestions": gaps,
    }}
