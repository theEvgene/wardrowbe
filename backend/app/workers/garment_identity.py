import logging
from pathlib import Path
from uuid import UUID

from app.config import get_settings
from app.services.dinov2_embedding import Dinov2EmbeddingProvider
from app.services.garment_identity_service import GarmentIdentityService
from app.workers.db import get_db_session

logger = logging.getLogger(__name__)


async def match_garment_identity(ctx: dict, item_id: str) -> dict:
    settings = get_settings()
    if not settings.garment_matching_enabled:
        return {"status": "skipped", "reason": "garment matching disabled", "item_id": item_id}

    provider = ctx.get("garment_embedding_provider")
    if provider is None:
        provider = Dinov2EmbeddingProvider()
        ctx["garment_embedding_provider"] = provider

    db = get_db_session(ctx)
    try:
        service = GarmentIdentityService(
            db,
            provider=provider,
            review_threshold=settings.garment_matching_review_threshold,
            storage_root=Path(settings.storage_path),
        )
        candidates = await service.analyze_primary_image(
            UUID(item_id), user_id=await _user_id(db, item_id)
        )
        logger.info("Garment matching found %d candidates for item %s", len(candidates), item_id)
        return {
            "status": "success",
            "item_id": item_id,
            "candidate_ids": [str(candidate.id) for candidate in candidates],
        }
    finally:
        await db.close()


async def _user_id(db, item_id: str) -> UUID:
    from sqlalchemy import select

    from app.models.item import ClothingItem

    return (
        await db.execute(select(ClothingItem.user_id).where(ClothingItem.id == UUID(item_id)))
    ).scalar_one()
