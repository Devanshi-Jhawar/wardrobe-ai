# Embedding Service

Building block 4 of wardrobe-ai. Turns a clothing photo into a **vector** (a list
of numbers) so the app can find similar items. It is fully independent of the
vision service — both just take an image; vision outputs labels, this outputs a
vector. It's the engine behind the wardrobe service's `/search`.

## Two backends (same output size, swap anytime)

| Backend | What it captures | Text search? | Install |
|---------|------------------|--------------|---------|
| **`color`** (default) | Color palette of the garment. Lightweight, no model download, runs anywhere. | No | nothing extra |
| `clip` | Real semantic meaning (a shirt vs a saree), the proper choice. | Yes ("navy office shirt") | `requirements-clip.txt` (heavy) |

Both emit 512-number vectors, so you can start on `color` today and switch to
`clip` later without changing the wardrobe service.

## Run it after cloning

Needs **Python 3.11+**.

```bash
cd services/embedding
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8003
```

Open **http://127.0.0.1:8003/docs** to try it.

## Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/embed` | Upload an image → `{embedding, dim, backend}`. (What the wardrobe service calls.) |
| POST | `/embed/text` | Text → vector, for word-based search. **CLIP only**; returns 501 on `color`. |
| GET | `/info` | Current backend, vector size, whether text is supported. |
| GET | `/health` | Liveness. |

## Example

```bash
curl -F "file=@shirt.jpg" http://127.0.0.1:8003/embed
# -> {"embedding":[0.01, 0.0, ...512 numbers...],"dim":512,"backend":"color"}
```

## Enable real CLIP embeddings later

```bash
pip install -r requirements-clip.txt      # torch + open_clip (~2 GB, one-time)
# set EMBEDDING_BACKEND=clip in .env (copy from .env.example)
uvicorn app.main:app --reload --port 8003
```

First run downloads the CLIP model once. If `torch` won't install on your Python
version, create the venv with Python 3.11 or 3.12 for this service.

## How it plugs into the wardrobe service

The wardrobe service already knows how to call this — see its `app/clients.py`
(`EMBEDDING_SERVICE_URL`, default `http://localhost:8003`). Once both this and the
vision service are running, set `ENABLE_ENRICHMENT=true` in the wardrobe service
and uploads get a vector automatically.
