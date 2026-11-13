# Agent service (block 6, Phase 2 — the brain)

It doesn't store clothes, preferences or call weather APIs itself — it
**orchestrates the other services** through a [LangGraph](https://langchain-ai.github.io/langgraph/)
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
| `gather`   | Calls **wardrobe**, **weather** (for the asked-about dates) and **memory** (likes, dislikes, feedback, recent wears). |
| `composer` | Picks one item per slot (top/bottom/footwear, +layer if cold, or a onepiece). Skips disliked and recently-worn items, prefers liked ones. |
| `critic`   | Checks completeness + occasion fit. Fails → loops back to `composer` (max 3). |
| `gap`      | Flags slots the wardrobe can't fill and suggests what to buy. |
| `remember` | Saves a dislike ("no frocks") to the **memory** service. |
| `answer`   | Shapes the final human-readable + structured reply. |

`planner` and `composer` are **rules-based** today (no API key needed). Their
signatures are frozen so an LLM version can drop in later via `AGENT_MODE=llm`.

## Run

```bash
cd services/agent
python -m venv .venv && .venv/Scripts/pip install -r requirements.txt
.venv/Scripts/uvicorn app.main:app --port 8000
```

Needs the wardrobe (8001), weather (8004) and memory (8006) services for full
answers, but degrades gracefully (thinner answers) if they're down. Without
memory it can't remember dislikes and says so.

## Weather and dates

The agent asks the weather service for the days the request is about —
"tomorrow", "saturday", "this weekend", "next week", or "a 4-day trip" starting
today — and reads each day's `label` (hot / mild / cold), `max`, `rainy` and
`needs.layer_for_evening`. It adds a jacket only when a day is cold, and over
several days packs for the coldest / rainiest one. Forecasts go 16 days ahead.

## Memory

All preferences live in the memory service (`GET /memory/{user_id}`):
dislike words and thumbs-down items are filtered out, like words and
thumbs-up items score higher, and items worn within `avoid_repeat_days` are
skipped unless nothing else fits the slot.

## Endpoints

| Method | Path | Body / query | Purpose |
|--------|------|--------------|---------|
| GET  | `/health`   | — | Agent status + which downstream services are reachable. |
| POST | `/agent`    | `{query, user_id}` | Main entry — any request through the full graph. |
| POST | `/outfit`   | `{occasion, city, when, user_id}` | Structured recommendation. |
| POST | `/feedback` | `{dislike, user_id}` | Remember a preference directly. |
| GET  | `/wardrobe` | `?user_id=` | The user's wardrobe (proxied). |

## Config (env vars)

`WARDROBE_URL`, `WEATHER_URL`, `MEMORY_URL` (`http://localhost:8006`),
`VISION_URL`, `EMBED_URL`, `AGENT_PORT` (8000), `AGENT_MODE` (`rules`),
`AGENT_MAX_ATTEMPTS` (3).
