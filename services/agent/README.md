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
| `planner`  | Reads the sentence → intent (recommend/trip/gap/save_preference), occasion, city, dates, and the words describing the clothes (for search). |
| `gather`   | Calls **wardrobe**, **weather** (for the asked-about dates) and **memory** (likes, dislikes, feedback, recent wears); ranks item photos via **embedding** + wardrobe search when CLIP is on. |
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

## Search ("I want to wear my red saree")

The planner keeps only what the request says about the clothes — it drops
filler ("what should I wear"), the occasion, city and dates — so
"I want to wear my red saree" searches `red saree`, while
"what should I wear to office tomorrow?" searches nothing. Matching items get
up to +5 in the composer (an occasion match is +10); search never hides items.

1. **Tag match (always on):** each word found in an item's color, category,
   style, pattern, material, occasion or season tags adds +3. Handles colors
   and garment names ("red", "saree", "white t-shirt").
2. **CLIP photo search (optional):** for words no item is tagged with
   ("ethnic", "traditional", "formal"), the agent turns the words into a
   vector (`POST /embed/text`, port 8003) and ranks the item photos with the
   wardrobe's `POST /wardrobe/search`. Only the `clip` embedding backend can do
   this; with the default `color` backend the embedding service answers 501
   and this step is skipped silently.

A dress / saree replaces a top + bottom when it beats both by 3+ points (an
occasion or search match), or when there's no complete top + bottom pair.

**Turning on CLIP:**

```bash
cd services/embedding
pip install -r requirements.txt -r requirements-clip.txt   # torch, ~1 GB with the model
# .env:  EMBEDDING_BACKEND=clip
uvicorn app.main:app --port 8003
```

Then set `ENABLE_ENRICHMENT=true` in `services/wardrobe/.env` so new uploads
get CLIP photo vectors. Items uploaded while the `color` backend was on have
color vectors, which can't be compared with CLIP text — re-upload them (or
clear their `embedding`) after switching. `debug.search_matches` in the
`/agent` reply shows how many items CLIP ranked (0 = CLIP search not used).

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
`EMBED_URL` (`http://localhost:8003`), `VISION_URL`, `AGENT_PORT` (8000),
`AGENT_MODE` (`rules`), `AGENT_MAX_ATTEMPTS` (3), `AGENT_HTTP_TIMEOUT` (10 s),
`AGENT_EMBED_TIMEOUT` (30 s — CLIP on CPU can be slow on its first call).
