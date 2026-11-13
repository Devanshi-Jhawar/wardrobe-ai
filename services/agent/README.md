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
| `composer` | Picks one item per slot (top/bottom/footwear, +layer if cold, or a onepiece), then accessories. Uses the weather's advice, skips disliked and recently-worn items, prefers liked ones. Trips: one outfit per day. |
| `critic`   | Checks completeness + occasion fit. Fails → loops back to `composer` (max 3). |
| `gap`      | Flags slots the wardrobe can't fill and suggests what to buy. |
| `remember` | Saves likes / dislikes ("no frocks", "I love blue") to the **memory** service. |
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

## Clothing vocabulary (`app/slots.py`)

Vision tags uploads with its model's 23 classes (`data.yaml`), weather speaks
its own words (`TYPES` in `weather/main.py`), and users can type anything.
`slots.py` maps every vision class to an outfit slot and to the weather's
words; hand-typed categories ("Kurtis", "Heels", "Palazzo pants") fall back to
keywords. Ethnic wear: Kurti / Kameez / Sherwani are tops, Shalwar / Sharara
bottoms, Anarkali / Maxi / Saree / Lehenga one-pieces, Dupatta an accessory.
`tests/test_vocabulary.py` fails if a vision class or weather word is unmapped
— add new classes to `CATEGORIES` when the model is retrained.

Bottoms match the top's style when possible (kurti + sharara, t-shirt + jeans).

## Weather, dates and trips

The agent asks the weather service for the days the request is about —
"tomorrow", "saturday", "this weekend", "next week", or "a 4-day trip" starting
today (forecasts go 16 days ahead) — and uses everything each day returns:

- `label` (hot / mild / cold): a jacket only when cold; summer items when hot.
- `needs.types_prefer` / `types_avoid`: e.g. sandals over boots when hot.
  An item the weather advises against is used only if nothing else fits.
- `needs.materials_prefer` / `materials_avoid`: linen when hot, wool when cold.
- `rainy` + `needs.colors_avoid`: skips white, prefers quick-drying fabrics.
- `needs.accessories`: sunglasses / cap / scarf / gloves are added from the
  wardrobe when owned; the rest (sunscreen, umbrella) go in `carry`.

Occasions add accessories too: jewellery and a bag for weddings, festivals and
parties, a bag or watch for office; a dupatta goes with kurti / sharara looks.

**Trips** ("packing for a 4-day trip to Shimla", "this weekend in Goa") get a
plan per day, each against that day's forecast, plus a `packing_list` with
each item once and a `carry` list. Clothes don't repeat across days unless
nothing else suits — re-wearing shoes beats sandals in the cold. One outfit
covering several days uses what every day allows.

## Recording wears and ratings

The agent only knows what you wore if you tell it:

- **`POST /wear`** with the `item_ids` from an answer ("I'm wearing this"). Those
  items are skipped for `avoid_repeat_days` (3 by default, set per user in
  memory). Set `SYNC_WARDROBE_WEAR=true` in the memory service to also bump
  the wardrobe's `wear_count`.
- **`POST /rate`** — thumbs up / down on an outfit's ids or one item. Down:
  never suggested again. Up: ranked higher.
- **Likes and dislikes in chat:** "I love yellow and ethnic wear", "I don't
  like heels or skirts". A newer statement replaces an older opposite one.

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
| POST | `/wear`     | `{item_ids, user_id, worn_on?, occasion?, city?, note?}` | Log an outfit as worn. 400 for a future date, 503 if memory is down. |
| POST | `/rate`     | `{item_ids, liked, user_id, reason?}` | Thumbs up / down. |
| POST | `/feedback` | `{dislike?, like?, user_id}` | Remember a like / dislike word directly. |
| GET  | `/wardrobe` | `?user_id=` | The user's wardrobe (proxied). |

`/agent` answers have a `type`: `recommendation` (`outfit`, `item_ids`,
`carry`, `suggestions`), `trip_plan` (`days[]` each with `outfit` +
`item_ids`, `packing_list`, `carry`), `gap`, `preference_saved` /
`preference_not_saved`.

## Tests

```bash
cd services/agent
pip install -r requirements-dev.txt
python -m pytest                     # ~140 fast tests, no services needed
AGENT_LIVE=1 python -m pytest tests/test_live.py   # against running wardrobe, weather, memory
```

The fast tests build weather replies with the weather service's real
`clothing_needs()` and read the vision classes from the real `data.yaml`, so
a change in either service shows up here. The live tests check the agent and
each service still agree on their APIs (they create a random memory user).

## Config (env vars)

`WARDROBE_URL`, `WEATHER_URL`, `MEMORY_URL` (`http://localhost:8006`),
`EMBED_URL` (`http://localhost:8003`), `VISION_URL`, `AGENT_PORT` (8000),
`AGENT_MODE` (`rules`), `AGENT_MAX_ATTEMPTS` (3), `AGENT_HTTP_TIMEOUT` (10 s),
`AGENT_EMBED_TIMEOUT` (30 s — CLIP on CPU can be slow on its first call).
