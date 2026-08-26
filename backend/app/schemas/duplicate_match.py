from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, model_validator


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
