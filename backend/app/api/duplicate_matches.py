from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.schemas.duplicate_match import (
    DuplicateMatchDecisionRequest,
    DuplicateMatchResponse,
    DuplicateMatchReviewItem,
    DuplicateMatchReviewResponse,
)
from app.services.duplicate_match_service import DuplicateMatchService
from app.utils.auth import get_current_user

router = APIRouter(prefix="/duplicate-matches", tags=["Duplicate matches"])


@router.get("", response_model=list[DuplicateMatchReviewResponse])
async def list_pending_duplicate_matches(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[DuplicateMatchReviewResponse]:
    matches = await DuplicateMatchService(db).list_pending(current_user.id)
    return [
        DuplicateMatchReviewResponse(
            **DuplicateMatchResponse.model_validate(candidate).model_dump(),
            item_low=DuplicateMatchReviewItem.model_validate(item_low),
            item_high=DuplicateMatchReviewItem.model_validate(item_high),
        )
        for candidate, item_low, item_high in matches
    ]


@router.post("/{candidate_id}/decision", response_model=DuplicateMatchResponse)
async def decide_duplicate_match(
    candidate_id: UUID,
    request: DuplicateMatchDecisionRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> DuplicateMatchResponse:
    service = DuplicateMatchService(db)
    if request.decision == "merge":
        candidate = await service.decide_merge(
            candidate_id, current_user.id, request.canonical_item_id
        )
    else:
        candidate = await service.decide_keep_separate(candidate_id, current_user.id)
    return DuplicateMatchResponse.model_validate(candidate)
