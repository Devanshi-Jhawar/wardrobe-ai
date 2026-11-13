"""Node: remember — persist a preference the planner extracted.

Runs only for the save_preference intent ("I don't like frocks", "I love
blue"). It saves the likes or dislikes in the memory service, so every future
recommendation uses them, then leaves a confirmation for the answer node.
If the memory service is down, `memory_saved` is False and the answer says so.
"""
from .. import clients, prefs as prefs_mod
from ..state import OutfitState


def remember(state: OutfitState) -> dict:
    user_id = state.get("user_id") or "demo"
    things = state.get("preferences") or []
    if not things:
        return {"memory_saved": False}
    saved = clients.save_preferences(user_id, things, state.get("preference_kind") or "dislike")
    if saved is None:
        return {"memory_saved": False}
    prefs = prefs_mod.empty_prefs(available=True)
    prefs["likes"] = [str(x).lower() for x in saved.get("likes") or []]
    prefs["dislikes"] = [str(x).lower() for x in saved.get("dislikes") or []]
    return {"memory_saved": True, "prefs": prefs}
