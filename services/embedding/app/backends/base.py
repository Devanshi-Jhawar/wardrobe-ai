from abc import ABC, abstractmethod


class EmbeddingBackend(ABC):
    """Common interface every backend implements, so the API doesn't care which
    one is loaded. Both must emit vectors of `dim` numbers."""

    name: str
    dim: int
    model: str | None = None
    supports_text: bool = False

    @abstractmethod
    def embed_image(self, raw: bytes) -> list[float]:
        """Turn raw image bytes into a vector."""

    def embed_text(self, text: str) -> list[float]:
        """Turn text into a vector in the same space (CLIP only)."""
        raise NotImplementedError(f"{self.name} backend does not support text embeddings")
