# wardrobe-ai

A personal wardrobe AI assistant. You upload photos of your clothes, and the app
helps you decide what to wear — based on the occasion, season, weather, and your
own preferences.

The project is built as small, independent services (phase 1):

| # | Service | Job | Status |
|---|---------|-----|--------|
| 1 | **Wardrobe** | Stores your clothes (the digital closet) + CRUD | ✅ built |
| 2 | **Vision** | Looks at a photo and labels the garment (color, type…) | ✅ built |
| 3 | **Embedding** | Turns a photo into a vector for similarity search | ✅ built |
| 4 | **Weather** | Fetches the forecast and says what clothes each day needs | ✅ built |
| 5 | **Memory** | Remembers likes, dislikes, what you wore when, and feedback | ✅ built |

Phase 2 adds the **Agent** (block 6, port 8000): a LangGraph brain that takes a
plain request ("what do I wear to office tomorrow in Goa?") and orchestrates
the services above into an outfit. See [Block 6](#block-6-agent-service).
Phase 3 adds the **UI** (port 8080), the **Grok LLM planner**, **Postgres +
pgvector**, and Docker Compose to run it all with one command.

## Quick start: everything in Docker

You need **Docker Desktop** only. Postgres runs in a container, so there is
nothing else to install.

```bash
git lfs pull                     # the vision model (best.pt)
copy .env.example .env           # Windows   (cp on macOS / Linux)
# open .env and set XAI_API_KEY=... for the Grok planner (optional)
docker compose up --build        # first build takes a while (PyTorch for vision)
```

| Open | What |
|------|------|
| http://localhost:8080 | The app: stylist chat, wardrobe, preferences |
| http://localhost:8000/docs | The agent API (the gateway the UI uses) |
| http://localhost:8001/docs ... 8006/docs | Each service on its own |

Data lives in Docker volumes: `pgdata` (Postgres: wardrobe + memory databases)
and `uploads` (clothing photos). `docker compose down` keeps them;
`docker compose down -v` deletes them.

Without Docker, each service still runs on its own with SQLite (see each block
below), and the UI runs with `cd ui && npm install && npm run dev`
(http://localhost:5173, forwarding `/api` to the agent on 8000).

## The UI (`ui/`)

React + Vite + TypeScript, dark theme. Three pages:

- **Stylist**: chat with the agent. Outfits show as photo cards with the
  weather reasoning, "I'm wearing this" (logs a wear), Like / Not for me
  (thumbs up / down), and suggestions with shopping links. Trips show a card
  per day (forecast, that day's occasion, the outfit) plus a packing list.
- **Wardrobe**: upload photos (drag and drop, several at once; each is tagged
  by vision), filter by slot, open a piece to fix its tags, favourite it,
  re-analyse it, or remove it.
- **Preferences**: likes and dislikes, the no-repeat window, wear history.

The **Profile** box (bottom left) is the `user_id`; switch it to keep separate
wardrobes. The status panel shows which services and which planner are live.
The UI only talks to the agent; nginx (Docker) or Vite (dev) forwards `/api`.

---

## Block 1: Wardrobe service

The wardrobe service is the app's memory of what you own. It stores clothing
images + their details and lets you add, view, edit, and remove items. It does
**not** identify clothes by itself yet — that's the Vision service (block 2).

### Run it after cloning

You need **Python 3.11+** installed.

```bash
git clone https://github.com/Devanshi-Jhawar/wardrobe-ai.git
cd wardrobe-ai/services/wardrobe

python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux

pip install -r requirements.txt
uvicorn app.main:app --reload --port 8001
```

Then open **http://127.0.0.1:8001/docs** — an interactive page where you can try
every endpoint (upload a clothing photo, list items, etc.) without writing code.

That's it. It uses a local SQLite database and saves images to a local `storage/`
folder, so there's nothing else to install or configure.

### What you can do

| Action | Endpoint |
|--------|----------|
| Upload a clothing photo | `POST /wardrobe/items` |
| See / filter your clothes | `GET /wardrobe/items` |
| View one item | `GET /wardrobe/items/{id}` |
| Edit an item's details | `PATCH /wardrobe/items/{id}` |
| Remove an item | `DELETE /wardrobe/items/{id}` |
| Record wearing an item | `POST /wardrobe/items/{id}/wear` |
| Find similar clothes | `POST /wardrobe/search` |
| Check the service is alive | `GET /health` |

Full details and examples: [`services/wardrobe/README.md`](services/wardrobe/README.md).

> Note: until the Vision service exists, uploads don't auto-detect the garment.
> You can add details manually via the `attributes_json` field, or leave them
> blank and the item is saved as `pending`.

---

## Block 3: Embedding service

Turns a clothing photo into a **vector** (list of numbers) so the app can find
similar items — the engine behind the wardrobe's `/search`. Independent of the
vision service. Ships with a lightweight color-based backend that runs with no
model download, and an optional CLIP backend for real semantic + text search.

### Run it after cloning

```bash
cd services/embedding
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8003
```

Then open **http://127.0.0.1:8003/docs**.

Full details, backends, and how to enable CLIP: [`services/embedding/README.md`](services/embedding/README.md).

---

## Block 2: Vision service

Looks at a clothing photo and returns `category` (one of the 23 YOLO classes),
`color`, `pattern`, `material`, `style`, `occasion` and `season`, which are the fields
the wardrobe stores. It runs the YOLO model in `runs/detect/train-2/weights/best.pt`.

### Run it after cloning

```bash
git lfs pull                    # gets the real best.pt (19 MB)
cd services/vision
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
uvicorn main:app --reload --port 8002
```

Then open **http://127.0.0.1:8002/docs**. To have uploads tagged automatically,
start vision (8002) and embedding (8003), set `ENABLE_ENRICHMENT=true` in
`services/wardrobe/.env`, and restart the wardrobe.

Full details and known model weak spots: [`services/vision/README.md`](services/vision/README.md).

---

## Block 4: Weather service

Gives the forecast for a city or dates (free Open-Meteo data, no key) and, for each
day, what kind of clothing it needs: warmth, types and materials to prefer or
avoid, waterproof, evening layer, accessories. It doesn't pick clothes itself;
`outfit_demo.py` shows how that's matched against the wardrobe.

### Run it after cloning

```bash
cd services/weather
pip install -r requirements.txt
uvicorn main:app --reload --port 8004
```

Then open **http://127.0.0.1:8004/docs**. With the wardrobe running:

```bash
python check_compat.py u1            # checks wardrobe and weather still fit
python outfit_demo.py Goa --user u1  # an outfit per day from u1's clothes
```

Full explanation: [`services/weather/GUIDE.md`](services/weather/GUIDE.md).

---

## Block 5: Memory service

The agents' notebook. Stores each user's likes and dislikes, which outfit they
wore on which day, and thumbs up / down on items. `GET /memory/{user_id}`
returns it all in one call, including `recently_worn_item_ids` so outfits don't
repeat within `avoid_repeat_days` (3 by default). Item ids are the wardrobe's.

### Run it after cloning

```bash
cd services/memory
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8006
```

Then open **http://127.0.0.1:8006/docs**. Set `SYNC_WARDROBE_WEAR=true` to also
bump the wardrobe's `wear_count` whenever an outfit is recorded.

Full explanation: [`services/memory/README.md`](services/memory/README.md).

---

## Block 6: Agent service

The brain. It reads a free-form request, works out the occasion, city and dates,
then pulls your clothes from the wardrobe (8001), the forecast for those dates
from weather (8004), and your likes, dislikes and recent wears from memory
(8006), and composes an outfit. Telling it "I don't like blazers" saves that
to the memory service.

### Run it after cloning

Start the wardrobe, weather and memory services first, then:

```bash
cd services/agent
pip install -r requirements.txt
uvicorn app.main:app --port 8000
```

Then open **http://127.0.0.1:8000/docs** and try `POST /agent` with
`{"query": "what should I wear to office tomorrow in Goa?", "user_id": "u1"}`.

**Grok planner:** set `XAI_API_KEY` (in `.env` for Docker, or the environment)
and the planner asks Grok to read the request, falling back to the rules if
the call fails. Without a key it uses the rules. `GET /health` shows which.

**Trips with a plan per day:** "4 day trip to Goa: day 1 beach, day 2 wedding,
day 3 sightseeing, day 4 flight home" dresses each day for its own occasion
against that day's forecast.

Full explanation: [`services/agent/README.md`](services/agent/README.md).
