"""Pass-through routes so a browser only ever talks to the agent.

The UI uploads photos, edits items, shows images and reads memory through
these; each one forwards to the wardrobe or memory service and returns its
reply (status code included). A service that's down becomes a 503.
"""
import httpx
from fastapi import APIRouter, File, Form, HTTPException, Request, Response, UploadFile

from . import config

router = APIRouter(tags=["gateway"])

UPLOAD_TIMEOUT = 90     # vision + embedding run during the upload


def _forward(method: str, url: str, timeout: float | None = None, **kwargs) -> Response:
    try:
        r = httpx.request(method, url, timeout=timeout or config.HTTP_TIMEOUT, **kwargs)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=503, detail=f"Service unreachable: {exc.__class__.__name__}")
    keep = {k: v for k, v in r.headers.items()
            if k.lower() in ("content-type", "cache-control")}
    return Response(content=r.content, status_code=r.status_code, headers=keep)


# ---------------------------------------------------------------- wardrobe ---

@router.post("/wardrobe/items")
async def upload_item(user_id: str = Form(...), file: UploadFile = File(...),
                      attributes_json: str | None = Form(None)):
    """Upload a clothing photo. With enrichment on, vision tags it on the way in."""
    raw = await file.read()
    data = {"user_id": user_id}
    if attributes_json:
        data["attributes_json"] = attributes_json
    return _forward("POST", f"{config.WARDROBE_URL}/wardrobe/items", timeout=UPLOAD_TIMEOUT,
                    data=data,
                    files={"file": (file.filename or "item.png", raw,
                                    file.content_type or "application/octet-stream")})


@router.get("/wardrobe/items/{item_id}")
def get_item(item_id: str, user_id: str):
    return _forward("GET", f"{config.WARDROBE_URL}/wardrobe/items/{item_id}",
                    params={"user_id": user_id})


@router.patch("/wardrobe/items/{item_id}")
async def update_item(item_id: str, user_id: str, request: Request):
    return _forward("PATCH", f"{config.WARDROBE_URL}/wardrobe/items/{item_id}",
                    params={"user_id": user_id}, json=await request.json())


@router.delete("/wardrobe/items/{item_id}")
def delete_item(item_id: str, user_id: str):
    return _forward("DELETE", f"{config.WARDROBE_URL}/wardrobe/items/{item_id}",
                    params={"user_id": user_id})


@router.post("/wardrobe/items/{item_id}/enrich")
def enrich_item(item_id: str, user_id: str):
    return _forward("POST", f"{config.WARDROBE_URL}/wardrobe/items/{item_id}/enrich",
                    params={"user_id": user_id}, timeout=UPLOAD_TIMEOUT)


@router.get("/wardrobe/items/{item_id}/image")
def item_image(item_id: str, user_id: str, thumb: bool = False):
    return _forward("GET", f"{config.WARDROBE_URL}/wardrobe/items/{item_id}/image",
                    params={"user_id": user_id, "thumb": str(thumb).lower()})


# ------------------------------------------------------------------ memory ---

@router.get("/memory")
def memory(user_id: str):
    """Likes, dislikes, recent wears and feedback in one call."""
    return _forward("GET", f"{config.MEMORY_URL}/memory/{user_id}")


@router.put("/memory/preferences")
async def set_preferences(user_id: str, request: Request):
    return _forward("PUT", f"{config.MEMORY_URL}/memory/{user_id}/preferences",
                    json=await request.json())


@router.get("/memory/history")
def history(user_id: str, limit: int = 50, offset: int = 0):
    return _forward("GET", f"{config.MEMORY_URL}/memory/{user_id}/history",
                    params={"limit": limit, "offset": offset})


@router.delete("/memory/worn/{entry_id}")
def delete_worn(entry_id: str, user_id: str):
    return _forward("DELETE", f"{config.MEMORY_URL}/memory/{user_id}/worn/{entry_id}")
