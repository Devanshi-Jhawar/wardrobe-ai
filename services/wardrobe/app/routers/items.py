import json

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from .. import clients, crud
from ..config import get_settings
from ..db import get_db
from ..schemas import ItemList, ItemOut, ItemUpdate
from ..storage import StorageError, save_image

router = APIRouter(prefix="/wardrobe/items", tags=["items"])
settings = get_settings()


@router.post("", response_model=ItemOut, status_code=201)
async def upload_item(
    user_id: str = Form(...),
    file: UploadFile = File(...),
    # Optional manual attributes (useful before enrichment exists, or to override it).
    attributes_json: str | None = Form(None),
    db: AsyncSession = Depends(get_db),
):
    raw = await file.read()
    try:
        image_url, thumbnail_url = save_image(raw)
    except StorageError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    fields: dict = {"user_id": user_id, "image_url": image_url, "thumbnail_url": thumbnail_url}

    if attributes_json:
        try:
            fields.update(json.loads(attributes_json))
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="attributes_json is not valid JSON")

    status = "pending"
    if settings.enable_enrichment:
        try:
            vision = await clients.analyze_image(raw, file.filename or "item.png")
            embedding = await clients.embed_image(raw, file.filename or "item.png")
            fields.update({k: v for k, v in vision.items() if k in _ENRICHABLE})
            fields["embedding"] = embedding
            status = "ready"
        except Exception:  # noqa: BLE001 — never let enrichment failure lose the upload
            status = "failed"
    elif attributes_json:
        status = "ready"

    fields["status"] = status
    item = await crud.create_item(db, **fields)
    return item


_ENRICHABLE = {"category", "color", "pattern", "material", "style", "occasion", "season", "attributes"}


@router.get("", response_model=ItemList)
async def list_items(
    user_id: str = Query(...),
    category: str | None = None,
    occasion: str | None = None,
    season: str | None = None,
    limit: int = Query(50, le=200),
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    total, items = await crud.list_items(
        db, user_id, category=category, occasion=occasion, season=season, limit=limit, offset=offset
    )
    return ItemList(total=total, items=items)


@router.get("/{item_id}", response_model=ItemOut)
async def get_item(item_id: str, user_id: str = Query(...), db: AsyncSession = Depends(get_db)):
    item = await crud.get_item(db, item_id, user_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@router.patch("/{item_id}", response_model=ItemOut)
async def update_item(
    item_id: str,
    payload: ItemUpdate,
    user_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    item = await crud.get_item(db, item_id, user_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return await crud.update_item(db, item, payload.model_dump(exclude_unset=True))


@router.delete("/{item_id}", status_code=204)
async def delete_item(item_id: str, user_id: str = Query(...), db: AsyncSession = Depends(get_db)):
    item = await crud.get_item(db, item_id, user_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    await crud.soft_delete(db, item)


@router.post("/{item_id}/wear", response_model=ItemOut)
async def wear_item(item_id: str, user_id: str = Query(...), db: AsyncSession = Depends(get_db)):
    item = await crud.get_item(db, item_id, user_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return await crud.mark_worn(db, item)
