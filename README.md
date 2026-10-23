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
