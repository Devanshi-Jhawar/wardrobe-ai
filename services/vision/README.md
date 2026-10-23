# Vision Service

Building block 2 of wardrobe-ai. Looks at a clothing photo and returns what it is,
its colours and related details. When `ENABLE_ENRICHMENT=true`, the wardrobe
service calls it on every upload and saves the answer with the item.

## How it works

1. **What is it?** The YOLO model trained in this repo
   (`runs/detect/train-2/weights/best.pt`, 23 clothing types) finds the garment
   in the photo, e.g. "Kurti" with 0.88 confidence.
2. **What colour?** It looks only inside the box the model drew, reduces it to
   its 6 main shades, and names them by hue (red, green, navy, maroon, beige…).
   One colour covering 60% or more, with no busy print inside, means `solid`;
   otherwise `patterned`.
3. **The rest:** `material`, `style`, `occasion` and `season` come from a table
   per category (`CATEGORY_INFO` in main.py). For example, Jeans means denim,
   casual, and suits spring, autumn and winter. A photo can't reliably show
   fabric, so material is a sensible guess, or empty when the category doesn't
   tell you (e.g. Dress).

If several items are in the photo, clothing wins over accessories, then the most
confident one. The others are listed in `attributes.other_items`. If the best
guess is only 10–25% sure, it is still used but flagged `low_confidence: true`,
so the app can ask the user to confirm.

## Run it after cloning

Needs **Python 3.11+** and the real model file. `best.pt` is stored with Git LFS,
so after cloning run `git lfs pull` (or download it from GitHub with the
download button and put it back in `runs/detect/train-2/weights/`).

```bash
cd services/vision
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt  # includes PyTorch, takes a few minutes
uvicorn main:app --reload --port 8002
```

Open **http://127.0.0.1:8002/docs**:
- `GET /health` shows `"model_loaded": true` when the model was found, or a `note` saying why not.
- `POST /analyze`: upload a photo.

The model is found automatically in `runs/detect/train-2/weights/`. To use
another file, set `MODEL_PATH`, or put it at `services/vision/models/best.pt`.

## Example

```json
{
  "category": "Sharara",
  "color": ["red", "beige"],
  "pattern": "patterned",
  "material": null,
  "style": "ethnic",
  "occasion": ["festival", "wedding"],
  "season": ["spring", "autumn"],
  "attributes": {"confidence": 0.86, "low_confidence": false, "weak_guesses": [],
                 "box": [83, 178, 416, 863], "other_items": [],
                 "color_shares": {"red": 0.53, "beige": 0.29, "maroon": 0.19}, "material_is_guess": false, "note": null}
}
```

## How it plugs into the wardrobe service

1. Start vision on 8002 and embedding on 8003.
2. In `services/wardrobe/.env` set `ENABLE_ENRICHMENT=true`, then start the wardrobe on 8001.
3. Upload a photo at http://127.0.0.1:8001/docs (`POST /wardrobe/items`) without
   `attributes_json`. The item comes back `"status": "ready"` with category and colours filled in.

The wardrobe calls vision and embedding together; if either is down, the item is
saved as `failed`.

## Changing the rules

- Wrong material or occasion for a category: edit its line in `CATEGORY_INFO`.
- Colour names: `color_name()` sorts by hue and uses brightness for dark shades.
- Too many wrong detections: raise `MIN_CONFIDENCE` (0.25). Guesses down to
  `WEAK_CONFIDENCE` (0.10) are used only when nothing better was found.

## Known model weak spots

See [`TEST_RESULTS.md`](TEST_RESULTS.md): short flared kurtis, jewellery on
stands and Lehenga vs Anarkali get mixed up. Classes with few training photos
(Shalwar 8, Kameez 20) are the least reliable. More training photos fix these.
