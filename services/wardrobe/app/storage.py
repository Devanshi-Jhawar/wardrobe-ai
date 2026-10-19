import io
import uuid
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from .config import get_settings

settings = get_settings()


class StorageError(Exception):
    pass


def _ensure_dirs() -> tuple[Path, Path]:
    base = settings.storage_dir
    images = base / "images"
    thumbs = base / "thumbnails"
    images.mkdir(parents=True, exist_ok=True)
    thumbs.mkdir(parents=True, exist_ok=True)
    return images, thumbs


def save_image(raw: bytes) -> tuple[str, str]:
    """Validate, persist the image + a thumbnail. Returns (image_path, thumb_path)."""
    if len(raw) > settings.max_image_bytes:
        raise StorageError("Image exceeds max size")

    try:
        img = Image.open(io.BytesIO(raw))
        img.verify()  # integrity check
        img = Image.open(io.BytesIO(raw))  # reopen; verify() leaves it unusable
    except (UnidentifiedImageError, OSError) as exc:
        raise StorageError("File is not a valid image") from exc

    images_dir, thumbs_dir = _ensure_dirs()
    name = f"{uuid.uuid4().hex}.png"

    image_path = images_dir / name
    img.convert("RGB").save(image_path, format="PNG")

    thumb = img.convert("RGB").copy()
    thumb.thumbnail((settings.thumbnail_size, settings.thumbnail_size))
    thumb_path = thumbs_dir / name
    thumb.save(thumb_path, format="PNG")

    return str(image_path), str(thumb_path)
