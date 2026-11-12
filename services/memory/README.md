# Memory Service

Building block 5 of wardrobe-ai. The agents' notebook: what each user likes and
dislikes, what they wore on which day, and their thumbs up / down on outfits.
The agents read it before choosing an outfit and write to it afterwards.

## Run

```bash
cd services/memory
python -m venv .venv
.venv\Scripts\activate          # Windows (PowerShell/cmd)
pip install -r requirements.txt
copy .env.example .env          # optional; defaults work out of the box
uvicorn app.main:app --reload --port 8006
```

Open http://localhost:8006/docs for the interactive API.

## Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET    | `/memory/{user_id}` | Everything the agents need in one call (see below). Unknown users get empty memory. |
| GET    | `/memory/{user_id}/preferences` | Likes, dislikes, `avoid_repeat_days`. |
| PUT    | `/memory/{user_id}/preferences` | Set them. Fields you leave out are kept. |
| POST   | `/memory/{user_id}/worn` | Record an outfit worn on a day (`item_ids`, optional `worn_on`, `occasion`, `city`, `note`). |
| GET    | `/memory/{user_id}/history` | Every worn outfit, newest first (`limit`, `offset`). |
| DELETE | `/memory/{user_id}/worn/{entry_id}` | Undo a wrong "worn" entry. |
| POST   | `/memory/{user_id}/feedback` | Thumbs up / down on items (`item_ids`, `liked`, optional `reason`). |
| GET    | `/health` | Liveness. |

`GET /memory/{user_id}` returns:

| Field | Meaning | Used by |
|---|---|---|
| `preferences.likes` / `dislikes` | Free words: colours, categories, styles ("blue", "Kurti", "heels") | composer prefers likes, gap drops dislikes |
| `recently_worn_item_ids` | Item ids worn in the last `avoid_repeat_days` (default 3) | critic avoids repeats |
| `liked_item_ids` / `disliked_item_ids` | From feedback; the latest opinion on an item wins | composer / gap |
| `recent_outfits` | Worn outfits from the last `recent_days` (default 14) | context, trip planning |

Item ids are the wardrobe's item ids, so memory never stores clothes itself.

## Example

```bash
curl -X PUT http://localhost:8006/memory/u1/preferences \
     -H "Content-Type: application/json" \
     -d '{"likes":["blue","ethnic"],"dislikes":["yellow"],"avoid_repeat_days":3}'

curl -X POST http://localhost:8006/memory/u1/worn \
     -H "Content-Type: application/json" \
     -d '{"item_ids":["<kurti id>","<jeans id>"],"occasion":"office","city":"Goa"}'

curl -X POST http://localhost:8006/memory/u1/feedback \
     -H "Content-Type: application/json" \
     -d '{"item_ids":["<kurti id>"],"liked":false,"reason":"too warm"}'

curl http://localhost:8006/memory/u1
```

## Notes

- **DB:** SQLite (`memory.db`) like the wardrobe. Set `DATABASE_URL` for Postgres later.
- **Wear counts:** set `SYNC_WARDROBE_WEAR=true` and memory also calls the
  wardrobe's `POST /wardrobe/items/{id}/wear` for each item, so `wear_count`
  stays in step. If the wardrobe is down, the outfit is still saved.
- **Dates:** `worn_on` defaults to today; dates more than a day ahead are refused.
