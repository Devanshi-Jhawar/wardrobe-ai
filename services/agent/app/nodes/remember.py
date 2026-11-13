"""Node: remember — persist a preference the planner extracted.

Runs only for the save_preference intent ("I don't like frocks"). It writes
the dislike to the memory store so every future recommendation filters it out,
then leaves a confirmation for the answer node.
"""
from .. import memory_store
from ..state import OutfitState


def remember(state: OutfitState) -> dict:
    user_id = state.get("user_id") or "demo"
    thing = state.get("preference")
    if not thing:
        return {"prefs": memory_store.get_prefs(user_id)}
    prefs = memory_store.add_dislike(user_id, thing)
    return {"prefs": prefs}
