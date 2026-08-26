from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.item import (
    ClothingItem,
    DuplicateMatchCandidate,
    DuplicateMatchStatus,
    ItemStatus,
)


class DuplicateMatchService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def decide_merge(
        self, candidate_id: UUID, user_id: UUID, canonical_item_id: UUID
    ) -> DuplicateMatchCandidate:
        candidate = await self._get_candidate_for_update(candidate_id, user_id)
        if candidate.status != DuplicateMatchStatus.pending:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Duplicate match has already been decided",
            )

        pair_ids = {candidate.item_low_id, candidate.item_high_id}
        if canonical_item_id not in pair_ids:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Canonical item must be one of the matched items",
            )

        items = (
            (
                await self.db.execute(
                    select(ClothingItem)
                    .where(ClothingItem.id.in_(pair_ids), ClothingItem.user_id == user_id)
                    .with_for_update()
                )
            )
            .scalars()
            .all()
        )
        if len(items) != 2:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Matched item not found"
            )
        if any(item.canonical_item_id is not None for item in items):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A matched item has already been merged",
            )

        by_id = {item.id: item for item in items}
        canonical = by_id[canonical_item_id]
        duplicate_id = next(item_id for item_id in pair_ids if item_id != canonical_item_id)
        duplicate = by_id[duplicate_id]

        canonical.is_archived = False
        canonical.archive_reason = None
        duplicate.canonical_item_id = canonical.id
        duplicate.is_archived = True
        duplicate.status = ItemStatus.archived
        duplicate.archived_at = datetime.now(UTC)
        duplicate.archive_reason = "merged_duplicate"

        candidate.status = DuplicateMatchStatus.merged
        candidate.canonical_item_id = canonical.id
        candidate.decided_at = datetime.now(UTC)
        await self.db.commit()
        await self.db.refresh(candidate)
        return candidate

    async def decide_keep_separate(
        self, candidate_id: UUID, user_id: UUID
    ) -> DuplicateMatchCandidate:
        candidate = await self._get_candidate_for_update(candidate_id, user_id)
        if candidate.status != DuplicateMatchStatus.pending:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Duplicate match has already been decided",
            )

        item_count = len(
            (
                await self.db.execute(
                    select(ClothingItem.id).where(
                        ClothingItem.id.in_([candidate.item_low_id, candidate.item_high_id]),
                        ClothingItem.user_id == user_id,
                    )
                )
            )
            .scalars()
            .all()
        )
        if item_count != 2:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Matched item not found"
            )

        candidate.status = DuplicateMatchStatus.kept_separate
        candidate.decided_at = datetime.now(UTC)
        await self.db.commit()
        await self.db.refresh(candidate)
        return candidate

    async def _get_candidate_for_update(
        self, candidate_id: UUID, user_id: UUID
    ) -> DuplicateMatchCandidate:
        candidate = (
            await self.db.execute(
                select(DuplicateMatchCandidate)
                .where(
                    DuplicateMatchCandidate.id == candidate_id,
                    DuplicateMatchCandidate.user_id == user_id,
                )
                .with_for_update()
            )
        ).scalar_one_or_none()
        if candidate is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found")
        return candidate
