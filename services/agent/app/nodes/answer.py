"""Node 6: answer — turn the filled-in State into the final reply.

The last node. It reads whatever the earlier nodes produced and shapes a
single `final_answer` dict: a human-readable `message` plus structured fields
the API can return as JSON. It decides nothing new — it just presents.
"""
from ..state import OutfitState


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
        thing = state.get("preference") or "that"
        msg = f"Got it — I'll stop suggesting {thing}. I'll remember that from now on."
        return {"final_answer": {"type": "preference_saved",
                                 "message": msg,
                                 "remembered": thing}}

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

    # --- a recommendation (or trip) ---
    draft = state.get("draft_outfit") or {}
    chosen = draft.get("items", [])
    gaps = state.get("missing_items") or []

    if chosen:
        outfit_line = ", ".join(_describe(it) for it in chosen)
        msg = f"Here's an outfit: {outfit_line}."
        if draft.get("rationale"):
            msg += f" ({draft['rationale']})"
    else:
        msg = "I couldn't put a full outfit together from your current wardrobe."

    if gaps:
        msg += "\n\nTo complete the look, consider:\n- " + \
               "\n- ".join(g["suggestion"] for g in gaps)

    return {"final_answer": {
        "type": "recommendation",
        "message": msg,
        "outfit": [{"id": it.get("id"),
                    "category": it.get("category"),
                    "color": it.get("color"),
                    "image_url": it.get("image_url")} for it in chosen],
        "rationale": draft.get("rationale"),
        "critic_notes": state.get("critic_notes"),
        "attempts": state.get("attempts", 0),
        "suggestions": gaps,
    }}
