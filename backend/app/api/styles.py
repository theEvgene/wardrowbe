from collections import Counter
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.item import ClothingItem, ItemStatus
from app.models.user import User
from app.utils.auth import get_current_user

router = APIRouter(prefix="/styles", tags=["Styles"])


class DetectedStyle(BaseModel):
    style: str
    item_count: int


class DetectedStylesResponse(BaseModel):
    styles: list[DetectedStyle]


@router.get("/detected", response_model=DetectedStylesResponse)
async def list_detected_styles(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> DetectedStylesResponse:
    """Return normalized styles found on the current user's active canonical items."""

    result = await db.execute(
        select(ClothingItem.style).where(
            and_(
                ClothingItem.user_id == current_user.id,
                ClothingItem.status == ItemStatus.ready,
                ClothingItem.is_archived.is_(False),
                ClothingItem.canonical_item_id.is_(None),
                ClothingItem.type != "unknown",
            )
        )
    )

    counts: Counter[str] = Counter()
    for raw_styles in result.scalars().all():
        normalized = {
            style.strip().lower()
            for style in (raw_styles or [])
            if isinstance(style, str) and style.strip()
        }
        counts.update(normalized)

    return DetectedStylesResponse(
        styles=[DetectedStyle(style=style, item_count=counts[style]) for style in sorted(counts)]
    )
