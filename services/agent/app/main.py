"""The agent service (the 5th service) — HTTP front door to the LangGraph brain.

Endpoints (from the Phase-2 plan):
  GET  /health    — is the agent up, and which downstream services are reachable
  POST /agent     — the main entry: free-form query in, final answer out
  POST /outfit    — convenience: structured occasion/city/date -> recommendation
  POST /feedback   — record a preference directly ("I don't like frocks")
  GET  /wardrobe   — surface the user's wardrobe (proxied from the wardrobe service)
"""
from fastapi import FastAPI
from pydantic import BaseModel

from . import clients, config, memory_store
from .graph import AGENT, run_agent

app = FastAPI(title="Wardrobe AI — Agent", version="0.1.0")


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
    user_id: str = "demo"
    dislike: str                     # the thing to stop suggesting, e.g. "frocks"


# --- endpoints ---

@app.get("/health")
def health():
    return {
        "status": "ok",
        "mode": config.MODE,
        "services": {
            "wardrobe": clients.ping(config.WARDROBE_URL),
            "vision":   clients.ping(config.VISION_URL),
            "embedding": clients.ping(config.EMBED_URL),
            "weather":  clients.ping(config.WEATHER_URL),
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
            "attempts": state.get("attempts"),
            "critic_notes": state.get("critic_notes"),
            "wardrobe_count": len(state.get("wardrobe_items") or []),
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


@app.post("/feedback")
def feedback(req: FeedbackRequest):
    """Directly remember a dislike, without going through the graph."""
    prefs = memory_store.add_dislike(req.user_id, req.dislike)
    return {"status": "saved", "prefs": prefs}


@app.get("/wardrobe")
def wardrobe(user_id: str = "demo", limit: int = 200):
    """Show the user's wardrobe (proxied from the wardrobe service)."""
    items = clients.fetch_wardrobe(user_id, limit=limit)
    return {"user_id": user_id, "count": len(items), "items": items}
