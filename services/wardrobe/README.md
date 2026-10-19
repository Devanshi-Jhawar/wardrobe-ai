# Wardrobe Service

Building block 1 of wardrobe-ai. Pure persistence + image storage over clothing
items. Does **not** run YOLO or compute embeddings — those are separate services
(vision, embedding) wired in via `app/clients.py` behind the `ENABLE_ENRICHMENT` flag.

## Run

```bash
cd services/wardrobe
python -m venv .venv
.venv\Scripts\activate          # Windows (PowerShell/cmd)
pip install -r requirements.txt
copy .env.example .env          # optional; defaults work out of the box
uvicorn app.main:app --reload --port 8001
```

Open http://localhost:8001/docs for the interactive API.

## Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| POST   | `/wardrobe/items` | Upload a garment image → create item (multipart: `user_id`, `file`, optional `attributes_json`). |
| GET    | `/wardrobe/items` | List + filter (`user_id`, `category`, `occasion`, `season`, `limit`, `offset`). |
| GET    | `/wardrobe/items/{id}` | Fetch one. |
| PATCH  | `/wardrobe/items/{id}` | Edit attributes / favorite. |
| DELETE | `/wardrobe/items/{id}` | Soft delete. |
| POST   | `/wardrobe/items/{id}/wear` | Record a wear (count + timestamp). |
| POST   | `/wardrobe/search` | Nearest-neighbour search over embeddings (the agent's read path). |
| GET    | `/health` | Liveness. |

## Example

```bash
# Upload (no enrichment yet -> stored as "pending")
curl -F "user_id=u1" -F "file=@shirt.jpg" http://localhost:8001/wardrobe/items

# Upload with manual attributes -> stored as "ready"
curl -F "user_id=u1" -F "file=@shirt.jpg" \
     -F 'attributes_json={"category":"Shirt","color":["navy"],"occasion":["office"]}' \
     http://localhost:8001/wardrobe/items

# List office shirts
curl "http://localhost:8001/wardrobe/items?user_id=u1&category=Shirt&occasion=office"
```

## Notes / next steps

- **DB:** SQLite by default for zero-setup dev. Set `DATABASE_URL` to Postgres later.
  Tables are auto-created on startup — add Alembic before moving to Postgres.
- **Embeddings:** stored as JSON; search is brute-force cosine. On Postgres, migrate
  the `embedding` column to `pgvector` and swap `/search` to an indexed `<=>` query.
- **Enrichment:** set `ENABLE_ENRICHMENT=true` and point `VISION_SERVICE_URL` /
  `EMBEDDING_SERVICE_URL` at those services once they exist. Upload then fills
  attributes + embedding automatically and marks items `ready`.
- **Auth:** `user_id` is passed explicitly for now; replace with a real auth
  dependency when the API layer lands.
```
