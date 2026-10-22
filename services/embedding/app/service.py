from functools import lru_cache

from .backends.base import EmbeddingBackend
from .config import get_settings


@lru_cache
def get_backend() -> EmbeddingBackend:
    """Build the configured backend once and reuse it (CLIP loads its model here)."""
    settings = get_settings()

    if settings.embedding_backend == "clip":
        from .backends.clip import ClipBackend

        return ClipBackend(settings.clip_model, settings.clip_pretrained)

    from .backends.color import ColorBackend

    return ColorBackend(dim=settings.embed_dim)
