import io

from PIL import Image

from .base import EmbeddingBackend


class ClipBackend(EmbeddingBackend):
    """Real semantic embeddings via open_clip. Image and text land in the same
    vector space, so you can search the wardrobe with a photo OR with words like
    "navy office shirt". Requires requirements-clip.txt (torch + open_clip)."""

    name = "clip"
    supports_text = True

    def __init__(self, model_name: str, pretrained: str) -> None:
        try:
            import open_clip
            import torch
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "CLIP backend needs extra deps. Run:\n"
                "  pip install -r requirements-clip.txt"
            ) from exc

        self._torch = torch
        self._device = "cuda" if torch.cuda.is_available() else "cpu"
        self._model, _, self._preprocess = open_clip.create_model_and_transforms(
            model_name, pretrained=pretrained
        )
        self._model.eval().to(self._device)
        self._tokenizer = open_clip.get_tokenizer(model_name)
        self.model = f"{model_name}/{pretrained}"

        with torch.no_grad():
            probe = self._model.encode_text(self._tokenizer(["probe"]).to(self._device))
        self.dim = int(probe.shape[-1])

    def _normalize(self, feats) -> list[float]:
        feats = feats / feats.norm(dim=-1, keepdim=True)
        return feats.squeeze(0).cpu().tolist()

    def embed_image(self, raw: bytes) -> list[float]:
        img = Image.open(io.BytesIO(raw)).convert("RGB")
        tensor = self._preprocess(img).unsqueeze(0).to(self._device)
        with self._torch.no_grad():
            feats = self._model.encode_image(tensor)
        return self._normalize(feats)

    def embed_text(self, text: str) -> list[float]:
        tokens = self._tokenizer([text]).to(self._device)
        with self._torch.no_grad():
            feats = self._model.encode_text(tokens)
        return self._normalize(feats)
