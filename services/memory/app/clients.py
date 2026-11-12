"""Optional call to the wardrobe service, so its wear_count stays in step with memory."""
import httpx

from .config import get_settings

settings = get_settings()


async def mark_worn_in_wardrobe(user_id: str, item_ids: list[str]) -> list[str]:
    """Best effort: returns the ids the wardrobe didn't accept. Never raises."""
    failed: list[str] = []
    async with httpx.AsyncClient(timeout=10) as client:
        for item_id in item_ids:
            try:
                resp = await client.post(
                    f"{settings.wardrobe_service_url}/wardrobe/items/{item_id}/wear",
                    params={"user_id": user_id},
                )
                if resp.status_code != 200:
                    failed.append(item_id)
            except httpx.HTTPError:
                failed.append(item_id)
    return failed
