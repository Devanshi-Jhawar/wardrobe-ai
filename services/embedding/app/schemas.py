from pydantic import BaseModel


class EmbedResponse(BaseModel):
    embedding: list[float]
    dim: int
    backend: str


class TextEmbedRequest(BaseModel):
    text: str


class InfoResponse(BaseModel):
    backend: str
    dim: int
    supports_text: bool
    model: str | None = None
