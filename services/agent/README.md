# Agent service (Phase 2 — the brain)

The 5th service. It doesn't store clothes or call weather APIs itself — it
**orchestrates the other four services** through a [LangGraph](https://langchain-ai.github.io/langgraph/)
agent, turning a free-form request ("what do I wear to office tomorrow?") into a
concrete outfit, gap suggestions, or a saved preference.

## The graph

```
planner ─► (preference?) ─► remember ─► answer
          └►(otherwise)──► gather ─► (gap question?) ─► gap ─► answer
                                    └►(recommend/trip)► composer ─► critic
                                                                     │
                            ┌──── critic passed ──► gap ─► answer ───┘
                            └──── critic failed ──► composer   (replan, capped)
```

| Node | Does |
|------|------|
| `planner`  | Reads the sentence → intent (recommend/trip/gap/save_preference), occasion, city, dates. |
| `gather`   | Calls **wardrobe** + **weather** services and loads remembered **prefs**. |
| `composer` | Picks one item per slot (top/bottom/footwear, +layer if cold, or a onepiece). |
| `critic`   | Checks completeness + occasion fit. Fails → loops back to `composer` (max 3). |
| `gap`      | Flags slots the wardrobe can't fill and suggests what to buy. |
| `remember` | Persists a dislike ("no frocks") to the memory store. |
| `answer`   | Shapes the final human-readable + structured reply. |

`planner` and `composer` are **rules-based** today (no API key needed). Their
signatures are frozen so an LLM version can drop in later via `AGENT_MODE=llm`.

## Run

```bash
cd services/agent
python -m venv .venv && .venv/Scripts/pip install -r requirements.txt
.venv/Scripts/uvicorn app.main:app --port 8000
```

Needs the wardrobe (8001) and weather (8004) services for full answers, but
degrades gracefully (thinner answers) if they're down.

## Endpoints

| Method | Path | Body / query | Purpose |
|--------|------|--------------|---------|
| GET  | `/health`   | — | Agent status + which downstream services are reachable. |
| POST | `/agent`    | `{query, user_id}` | Main entry — any request through the full graph. |
| POST | `/outfit`   | `{occasion, city, when, user_id}` | Structured recommendation. |
| POST | `/feedback` | `{dislike, user_id}` | Remember a preference directly. |
| GET  | `/wardrobe` | `?user_id=` | The user's wardrobe (proxied). |

## Config (env vars)

`WARDROBE_URL`, `WEATHER_URL`, `VISION_URL`, `EMBED_URL`, `AGENT_PORT` (8000),
`AGENT_MODE` (`rules`), `AGENT_MAX_ATTEMPTS` (3), `AGENT_MEMORY_PATH`.
