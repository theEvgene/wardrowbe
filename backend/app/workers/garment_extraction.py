import asyncio
import logging
from typing import Any
from uuid import UUID

from sqlalchemy import select

from app.models.item import ClothingItem, ItemStatus
from app.services.garment_extraction_metrics import garment_extraction_metrics
from app.services.image_service import ImageService
from app.workers.db import get_db_session

logger = logging.getLogger(__name__)

_PERSISTED_RESULT_KEYS = {
    "outcome",
    "mode",
    "provider",
    "provider_version",
    "model",
    "garment_category",
    "transparent_path",
    "warning",
    "metrics",
}


async def remove_garment_background(image_path: str, item_type: str) -> dict[str, object]:
    service = ImageService()
    return await asyncio.to_thread(
        service.remove_background,
        image_path,
        (255, 255, 255),
        "garment",
        item_type,
    )


def _metadata(result: dict[str, object]) -> dict[str, object]:
    return {key: value for key, value in result.items() if key in _PERSISTED_RESULT_KEYS}


async def extract_item_garment(ctx: dict, item_id: str) -> dict[str, Any]:
    """Safely create one garment cutout after tagging has identified its type."""

    db = get_db_session(ctx)
    try:
        result = await db.execute(
            select(ClothingItem).where(ClothingItem.id == UUID(item_id)).with_for_update()
        )
        item = result.scalar_one_or_none()
        if item is None:
            return {"status": "skipped", "reason": "item missing", "item_id": item_id}
        if item.status != ItemStatus.ready or not item.image_path:
            return {"status": "skipped", "reason": "item not ready", "item_id": item_id}

        current = item.background_removal or {}
        if (
            current.get("outcome") == "accepted"
            and current.get("mode") == "garment"
            and current.get("transparent_path")
        ):
            return {"status": "skipped", "reason": "already accepted", "item_id": item_id}

        extraction = await remove_garment_background(item.image_path, item.type)
        metadata = _metadata(extraction)
        outcome = str(extraction.get("outcome", "failed"))

        # A failed/rejected retry may report its outcome, but must never replace
        # an active successful artifact. The row lock serializes this decision
        # with other automatic attempts.
        if outcome == "accepted" or current.get("outcome") != "accepted":
            item.background_removal = metadata
        if outcome == "accepted":
            item.original_image_path = str(extraction["original_backup_path"])

        await db.commit()
        metrics = dict(extraction.get("metrics") or {})
        await garment_extraction_metrics.record(
            outcome=outcome,
            garment_category=(
                str(extraction["garment_category"])
                if extraction.get("garment_category") is not None
                else None
            ),
            duration_ms=float(metrics.get("duration_ms", 0.0)),
            quality=metrics,
        )
        logger.info("Automatic garment extraction outcome=%s item=%s", outcome, item_id)
        return {"status": outcome, "item_id": item_id, "background_removal": metadata}
    except Exception as exc:
        logger.exception("Automatic garment extraction failed for %s", item_id)
        await db.rollback()
        return {"status": "failed", "item_id": item_id, "error": str(exc)}
    finally:
        await db.close()
