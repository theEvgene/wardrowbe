import math
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.item import (
    ClothingItem,
    DuplicateMatchCandidate,
    DuplicateMatchStatus,
    ItemImageEmbedding,
    TaggedBy,
)
from app.utils.clothing import ITEM_ROLE


@dataclass(frozen=True)
class EmbeddingResult:
    vector: list[float]


class GarmentEmbeddingProvider(Protocol):
    model: str
    model_revision: str
    preprocess_revision: str

    async def embed(self, image_path: Path) -> EmbeddingResult: ...


class GarmentIdentityService:
    def __init__(
        self,
        db: AsyncSession,
        provider: GarmentEmbeddingProvider,
        review_threshold: float,
        storage_root: Path,
    ):
        if not 0.0 <= review_threshold <= 1.0:
            raise ValueError("review_threshold must be between 0 and 1")
        self.db = db
        self.provider = provider
        self.review_threshold = review_threshold
        self.storage_root = storage_root

    async def analyze_primary_image(
        self, item_id: UUID, user_id: UUID
    ) -> list[DuplicateMatchCandidate]:
        item = (
            await self.db.execute(
                select(ClothingItem).where(
                    ClothingItem.id == item_id,
                    ClothingItem.user_id == user_id,
                    ClothingItem.canonical_item_id.is_(None),
                    ClothingItem.is_archived.is_(False),
                )
            )
        ).scalar_one_or_none()
        if item is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")

        result = await self.provider.embed(self.storage_root / item.image_path)
        vector = self._normalize(result.vector)
        embedding = await self._upsert_primary_embedding(item, vector)
        await self.db.flush()

        rows = (
            await self.db.execute(
                select(ItemImageEmbedding, ClothingItem)
                .join(ClothingItem, ClothingItem.id == ItemImageEmbedding.item_id)
                .where(
                    ItemImageEmbedding.user_id == user_id,
                    ItemImageEmbedding.item_id != item.id,
                    ItemImageEmbedding.item_image_id.is_(None),
                    ItemImageEmbedding.model == embedding.model,
                    ItemImageEmbedding.model_revision == embedding.model_revision,
                    ItemImageEmbedding.preprocess_revision == embedding.preprocess_revision,
                    ClothingItem.canonical_item_id.is_(None),
                    ClothingItem.is_archived.is_(False),
                )
            )
        ).all()

        candidates: list[DuplicateMatchCandidate] = []
        for other_embedding, other_item in rows:
            if len(other_embedding.embedding) != len(vector):
                continue
            score = sum(
                left * right for left, right in zip(vector, other_embedding.embedding, strict=True)
            )
            if score < self.review_threshold:
                continue
            if self._manual_roles_incompatible(item, other_item):
                continue

            candidate = await self._record_pending_candidate(item, other_item, score)
            if candidate is not None:
                candidates.append(candidate)

        await self.db.commit()
        return candidates

    async def _upsert_primary_embedding(
        self, item: ClothingItem, vector: list[float]
    ) -> ItemImageEmbedding:
        embedding = (
            await self.db.execute(
                select(ItemImageEmbedding).where(
                    ItemImageEmbedding.item_id == item.id,
                    ItemImageEmbedding.item_image_id.is_(None),
                    ItemImageEmbedding.model == self.provider.model,
                    ItemImageEmbedding.model_revision == self.provider.model_revision,
                    ItemImageEmbedding.preprocess_revision == self.provider.preprocess_revision,
                )
            )
        ).scalar_one_or_none()
        if embedding is None:
            embedding = ItemImageEmbedding(
                user_id=item.user_id,
                item_id=item.id,
                source_path=item.image_path,
                embedding=vector,
                dimensions=len(vector),
                model=self.provider.model,
                model_revision=self.provider.model_revision,
                preprocess_revision=self.provider.preprocess_revision,
            )
            self.db.add(embedding)
        else:
            embedding.source_path = item.image_path
            embedding.embedding = vector
            embedding.dimensions = len(vector)
        return embedding

    async def _record_pending_candidate(
        self, item: ClothingItem, other_item: ClothingItem, score: float
    ) -> DuplicateMatchCandidate | None:
        low_id, high_id = sorted((item.id, other_item.id))
        candidate = (
            await self.db.execute(
                select(DuplicateMatchCandidate).where(
                    DuplicateMatchCandidate.item_low_id == low_id,
                    DuplicateMatchCandidate.item_high_id == high_id,
                )
            )
        ).scalar_one_or_none()
        if candidate is not None and candidate.status != DuplicateMatchStatus.pending:
            return None

        matcher_revision = (
            f"{self.provider.model}:{self.provider.model_revision}:"
            f"{self.provider.preprocess_revision}"
        )
        evidence = {
            "visual": {
                "cosine_score": score,
                "review_threshold": self.review_threshold,
                "model": self.provider.model,
                "model_revision": self.provider.model_revision,
                "preprocess_revision": self.provider.preprocess_revision,
            },
            "metadata": {
                "item_type": item.type,
                "other_item_type": other_item.type,
                "types_match": item.type.lower() == other_item.type.lower(),
                "both_user_confirmed": (
                    item.tagged_by == TaggedBy.manual and other_item.tagged_by == TaggedBy.manual
                ),
            },
        }
        if candidate is None:
            candidate = DuplicateMatchCandidate(
                user_id=item.user_id,
                item_low_id=low_id,
                item_high_id=high_id,
                status=DuplicateMatchStatus.pending,
                cosine_score=score,
                matcher_revision=matcher_revision,
                evidence=evidence,
            )
            self.db.add(candidate)
        elif candidate.cosine_score is None or score > float(candidate.cosine_score):
            candidate.cosine_score = score
            candidate.matcher_revision = matcher_revision
            candidate.evidence = evidence
        return candidate

    @staticmethod
    def _manual_roles_incompatible(item: ClothingItem, other_item: ClothingItem) -> bool:
        if item.tagged_by != TaggedBy.manual or other_item.tagged_by != TaggedBy.manual:
            return False
        role = ITEM_ROLE.get(item.type.lower())
        other_role = ITEM_ROLE.get(other_item.type.lower())
        return role is not None and other_role is not None and role != other_role

    @staticmethod
    def _normalize(vector: list[float]) -> list[float]:
        magnitude = math.sqrt(sum(value * value for value in vector))
        if not vector or not math.isfinite(magnitude) or magnitude == 0:
            raise ValueError("Embedding must be a finite, non-zero vector")
        normalized = [float(value / magnitude) for value in vector]
        if not all(math.isfinite(value) for value in normalized):
            raise ValueError("Embedding must contain only finite values")
        return normalized
