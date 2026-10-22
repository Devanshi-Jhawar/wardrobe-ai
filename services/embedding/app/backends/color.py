import io
import math

from PIL import Image, UnidentifiedImageError

from .base import EmbeddingBackend


class ColorBackend(EmbeddingBackend):
    """Dependency-free visual embedding: a normalized RGB color histogram.

    The image is shrunk to 64x64, then every pixel is spread across the
    bins x bins x bins color buckets using *soft* (trilinear) assignment: a
    pixel near a bin edge contributes to both neighboring bins by weight. This
    means two similar colors overlap in bin space and score as similar, instead
    of a tiny color shift flipping a pixel into a different bucket. The weighted
    bucket totals, L2-normalized, are the vector.

    Items with similar color palettes get similar vectors, so the wardrobe's
    /search returns visually-alike clothes. It is NOT semantic (it can't tell a
    shirt from a saree of the same color) — that's what the CLIP backend is for.
    Same output size either way, so nothing downstream changes.
    """

    name = "color"
    supports_text = False

    def __init__(self, dim: int = 512) -> None:
        self.bins = max(2, round(dim ** (1 / 3)))  # 512 -> 8 bins
        self.dim = self.bins ** 3
        self.model = f"rgb-histogram-{self.bins}bins-soft"

    def _soft_bins(self, value: int, step: float) -> tuple[tuple[int, float], tuple[int, float]]:
        """Split one channel value across its two nearest bins (trilinear)."""
        pos = value / step - 0.5          # bin-center coordinate
        lo = math.floor(pos)
        frac = pos - lo
        lo_c = min(max(lo, 0), self.bins - 1)
        hi_c = min(max(lo + 1, 0), self.bins - 1)
        return (lo_c, 1.0 - frac), (hi_c, frac)

    def embed_image(self, raw: bytes) -> list[float]:
        try:
            img = Image.open(io.BytesIO(raw)).convert("RGB").resize((64, 64))
        except (UnidentifiedImageError, OSError) as exc:
            raise ValueError("File is not a valid image") from exc

        bins = self.bins
        step = 256 / bins
        hist = [0.0] * self.dim
        for r, g, b in img.getdata():
            rbins = self._soft_bins(r, step)
            gbins = self._soft_bins(g, step)
            bbins = self._soft_bins(b, step)
            for ri, wr in rbins:
                for gi, wg in gbins:
                    for bi, wb in bbins:
                        w = wr * wg * wb
                        if w:
                            hist[ri * bins * bins + gi * bins + bi] += w

        norm = math.sqrt(sum(v * v for v in hist))
        if norm > 0:
            hist = [v / norm for v in hist]
        return hist
