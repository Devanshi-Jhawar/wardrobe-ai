"""Node: remember — persist a preference the planner extracted.

Runs only for the save_preference intent ("I don't like frocks"). It adds the
dislike to the user's preferences in the memory service, so every future
recommendation filters it out, then leaves a confirmation for the answer node.
If the memory service is down, `memory_saved` is False and the answer says so.
"""
from .. import clients, prefs as prefs_mod
from ..state import OutfitState


def remember(state: OutfitState) -> dict:
    user_id = state.get("user_id") or "demo"
    thing = state.get("preference")
    if not thing:
        return {"memory_saved": False}
    saved = clients.add_dislike(user_id, thing)
    if saved is None:
        return {"memory_saved": False}
    prefs = prefs_mod.empty_prefs(available=True)
    prefs["likes"] = [str(x).lower() for x in saved.get("likes") or []]
    prefs["dislikes"] = [str(x).lower() for x in saved.get("dislikes") or []]
    return {"memory_saved": True, "prefs": prefs}
