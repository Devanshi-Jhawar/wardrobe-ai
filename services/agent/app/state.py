"""The shared "clipboard" that flows through every node of the agent.

Each node reads the fields it needs and writes back the fields it produces.
`total=False` means every field is optional — the State starts nearly empty
(just the user's query) and fills up as it passes through the graph.
"""
from typing import TypedDict


class OutfitState(TypedDict, total=False):
    # --- input (set before the graph runs) ---
    query: str                 # the raw user request
    user_id: str

    # --- written by: planner ---
    intent: str                # recommend | trip | gap | save_preference
    occasion: str | None       # office, party, wedding, festival, gym, date, casual
    city: str | None           # e.g. "Goa" (None if not mentioned)
    dates: dict                # {"relative": "tomorrow"} or {"count": 4}
    preference: str | None     # for save_preference, e.g. "frocks"

    # --- written by: gather ---
    wardrobe_items: list[dict]
    weather: dict | None
    prefs: dict | None

    # --- written by: composer ---
    draft_outfit: dict | None

    # --- written by: critic ---
    critic_passed: bool | None
    critic_notes: str | None
    attempts: int

    # --- written by: gap ---
    missing_items: list[dict]

    # --- written by: answer ---
    final_answer: dict | None
