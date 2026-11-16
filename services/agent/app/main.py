"""The agent service (block 6) — HTTP front door to the LangGraph brain.

Endpoints:
  GET  /health    — is the agent up, and which downstream services are reachable
  POST /agent     — the main entry: free-form query in, final answer out
  POST /outfit    — convenience: structured occasion/city/date -> recommendation
  POST /wear      — "I'm wearing this": log an outfit as worn (feeds don't-repeat)
  POST /rate      — thumbs up / down on a suggested outfit or item
  POST /feedback  — remember a like / dislike word directly ("frocks", "blue")
  GET  /wardrobe  — surface the user's wardrobe (proxied from the wardrobe service)

Plus the pass-through routes in gateway.py (upload, edit, delete, images,
memory), so the UI only needs to reach this one service.
"""
from datetime import date

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, model_validator

from . import clients, config, gateway, llm
from .graph import run_agent
from .slots import slot_of

app = FastAPI(title="Wardrobe AI — Agent", version="0.3.0")
app.add_middleware(CORSMiddleware, allow_origins=config.CORS_ORIGINS,
                   allow_methods=["*"], allow_headers=["*"])
app.include_router(gateway.router)


# --- request bodies ---

class AgentRequest(BaseModel):
    query: str
    user_id: str = "demo"


class OutfitRequest(BaseModel):
    user_id: str = "demo"
    occasion: str | None = None
    city: str | None = None
    when: str | None = None          # e.g. "tomorrow", "this weekend"
    query: str | None = None         # optional free-form, overrides the above


class FeedbackRequest(BaseModel):
    """Remember a like or dislike word. Send `dislike`, `like`, or both."""
    user_id: str = "demo"
    dislike: str | None = None       # stop suggesting this, e.g. "frocks"
    like: str | None = None          # prefer this, e.g. "blue"

    @model_validator(mode="after")
    def _one_of(self):
        if not (self.dislike or self.like):
            raise ValueError("send `dislike` or `like`")
        return self


class WearRequest(BaseModel):
    """The outfit the user actually put on — usually the ids from /agent's answer."""
    user_id: str = "demo"
    item_ids: list[str] = Field(..., min_length=1)
    worn_on: date | None = None      # defaults to today
    occasion: str | None = None
    city: str | None = None
    note: str | None = None


class RateRequest(BaseModel):
    """Thumbs up / down on a suggested outfit (all its ids) or a single item."""
    user_id: str = "demo"
    item_ids: list[str] = Field(..., min_length=1)
    liked: bool
    reason: str | None = None        # e.g. "too warm"


# --- endpoints ---

@app.get("/health")
def health():
    return {
        "status": "ok",
        "mode": config.MODE,
        "llm": llm.status(),
        "services": {
            "wardrobe": clients.ping(config.WARDROBE_URL),
            "vision":   clients.ping(config.VISION_URL),
            "embedding": clients.ping(config.EMBED_URL),
            "weather":  clients.ping(config.WEATHER_URL),
            "memory":   clients.ping(config.MEMORY_URL),
        },
    }


@app.post("/agent")
def agent(req: AgentRequest):
    """Run any request through the full planner→...→answer graph."""
    state = run_agent(req.query, req.user_id)
    return {
        "answer": state.get("final_answer"),
        "intent": state.get("intent"),
        "debug": {
            "occasion": state.get("occasion"),
            "city": state.get("city"),
            "dates": state.get("dates"),
            "itinerary": state.get("itinerary"),
            "planner": state.get("planner_source"),
            "attempts": state.get("attempts"),
            "critic_notes": state.get("critic_notes"),
            "wardrobe_count": len(state.get("wardrobe_items") or []),
            # What was searched for, and how many items CLIP ranked
            # (0 = CLIP search off: color backend, no vectors, or nothing to search).
            "search_text": state.get("search_text"),
            "search_matches": len(state.get("search_scores") or {}),
        },
    }


@app.post("/outfit")
def outfit(req: OutfitRequest):
    """Structured recommendation request, composed into a query for the graph."""
    if req.query:
        q = req.query
    else:
        bits = ["what should I wear"]
        if req.occasion:
            bits.append(f"for {req.occasion}")
        if req.when:
            bits.append(req.when)
        if req.city:
            bits.append(f"in {req.city}")
        q = " ".join(bits) + "?"
    state = run_agent(q, req.user_id)
    return {"answer": state.get("final_answer"), "resolved_query": q}


@app.post("/wear", status_code=201)
def wear(req: WearRequest):
    """Log an outfit as worn. Those items are then skipped for the user's
    avoid_repeat_days (memory service; 3 days by default)."""
    try:
        entry = clients.record_worn(req.user_id, req.item_ids, req.worn_on,
                                    req.occasion, req.city, req.note)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if entry is None:
        raise HTTPException(status_code=503, detail="Memory service unreachable")
    return {"status": "recorded", "entry": entry}


@app.post("/rate", status_code=201)
def rate(req: RateRequest):
    """Thumbs up / down. Disliked items stop being suggested; liked ones rank higher."""
    fb = clients.rate_items(req.user_id, req.item_ids, req.liked, req.reason)
    if fb is None:
        raise HTTPException(status_code=503, detail="Memory service unreachable")
    return {"status": "saved", "feedback": fb}


@app.post("/feedback")
def feedback(req: FeedbackRequest):
    """Directly remember a like and/or dislike word (in the memory service)."""
    prefs = None
    for kind, thing in (("dislike", req.dislike), ("like", req.like)):
        if thing:
            prefs = clients.save_preferences(req.user_id, [thing], kind)
            if prefs is None:
                raise HTTPException(status_code=503, detail="Memory service unreachable")
    return {"status": "saved", "prefs": prefs}


@app.get("/wardrobe")
def wardrobe(user_id: str = "demo", limit: int = 200):
    """Show the user's wardrobe (proxied from the wardrobe service)."""
    items = clients.fetch_wardrobe(user_id, limit=limit)
    # The outfit slot of each item (top, bottom, onepiece, footwear, outerwear,
    # accessory, or None if untagged), so a UI can group without its own map.
    for it in items:
        it["slot"] = slot_of(it.get("category"))
    return {"user_id": user_id, "count": len(items), "items": items}
