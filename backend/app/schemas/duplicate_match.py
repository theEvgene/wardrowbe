from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, computed_field, model_validator

from app.utils.signed_urls import sign_image_url


class DuplicateMatchDecisionRequest(BaseModel):
    decision: Literal["merge", "keep_separate"]
    canonical_item_id: UUID | None = None

    @model_validator(mode="after")
    def validate_canonical_choice(self):
        if self.decision == "merge" and self.canonical_item_id is None:
            raise ValueError("canonical_item_id is required for merge")
        if self.decision == "keep_separate" and self.canonical_item_id is not None:
            raise ValueError("canonical_item_id is only valid for merge")
        return self


class DuplicateMatchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    item_low_id: UUID
    item_high_id: UUID
    status: str
    canonical_item_id: UUID | None = None
    cosine_score: Decimal | None = None
    matcher_revision: str
    evidence: dict
    decided_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class DuplicateMatchReviewItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    type: str
    name: str | None = None
    image_path: str
    thumbnail_path: str | None = None
    created_at: datetime

    @computed_field
    @property
    def image_url(self) -> str:
        return sign_image_url(self.image_path)

    @computed_field
    @property
    def thumbnail_url(self) -> str | None:
        return sign_image_url(self.thumbnail_path) if self.thumbnail_path else None


class DuplicateMatchReviewResponse(DuplicateMatchResponse):
    item_low: DuplicateMatchReviewItem
    item_high: DuplicateMatchReviewItem
