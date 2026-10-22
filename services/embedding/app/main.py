from fastapi import FastAPI, File, HTTPException, UploadFile

from .config import get_settings
from .schemas import EmbedResponse, InfoResponse, TextEmbedRequest
from .service import get_backend

settings = get_settings()
app = FastAPI(title="Embedding Service", version="0.1.0")


@app.get("/health", tags=["health"])
async def health():
    return {"status": "ok", "backend": settings.embedding_backend}


@app.get("/info", response_model=InfoResponse, tags=["info"])
async def info():
    b = get_backend()
    return InfoResponse(backend=b.name, dim=b.dim, supports_text=b.supports_text, model=b.model)


@app.post("/embed", response_model=EmbedResponse, tags=["embed"])
async def embed_image(file: UploadFile = File(...)):
    raw = await file.read()
    if len(raw) > settings.max_image_bytes:
        raise HTTPException(status_code=400, detail="Image exceeds max size")

    b = get_backend()
    try:
        vec = b.embed_image(raw)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return EmbedResponse(embedding=vec, dim=b.dim, backend=b.name)


@app.post("/embed/text", response_model=EmbedResponse, tags=["embed"])
async def embed_text(req: TextEmbedRequest):
    b = get_backend()
    try:
        vec = b.embed_text(req.text)
    except NotImplementedError as exc:
        raise HTTPException(status_code=501, detail=str(exc))
    return EmbedResponse(embedding=vec, dim=b.dim, backend=b.name)
