from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.item import (
    ClothingItem,
    DuplicateMatchCandidate,
    DuplicateMatchStatus,
    ItemStatus,
)


@pytest.mark.asyncio
async def test_merge_decision_keeps_both_items_and_aliases_one_to_chosen_canonical(
    client: AsyncClient,
    test_user,
    auth_headers,
    db_session: AsyncSession,
):
    canonical = ClothingItem(
        user_id=test_user.id,
        type="shirt",
        name="Blue shirt",
        image_path=f"test/{uuid4()}.jpg",
        status=ItemStatus.ready,
    )
    duplicate = ClothingItem(
        user_id=test_user.id,
        type="shirt",
        name="Same blue shirt, back",
        image_path=f"test/{uuid4()}.jpg",
        status=ItemStatus.ready,
    )
    db_session.add_all([canonical, duplicate])
    await db_session.flush()

    candidate = DuplicateMatchCandidate(
        user_id=test_user.id,
        item_low_id=min(canonical.id, duplicate.id),
        item_high_id=max(canonical.id, duplicate.id),
        status=DuplicateMatchStatus.pending,
        cosine_score=0.91,
        matcher_revision="test-v1",
    )
    db_session.add(candidate)
    await db_session.commit()
    canonical_id = canonical.id
    duplicate_id = duplicate.id

    response = await client.post(
        f"/api/v1/duplicate-matches/{candidate.id}/decision",
        headers=auth_headers,
        json={"decision": "merge", "canonical_item_id": str(canonical_id)},
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "merged"
    assert response.json()["canonical_item_id"] == str(canonical_id)

    db_session.expire_all()
    rows = (
        (
            await db_session.execute(
                select(ClothingItem).where(ClothingItem.id.in_([canonical_id, duplicate_id]))
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 2

    persisted = {item.id: item for item in rows}
    assert persisted[canonical_id].canonical_item_id is None
    assert persisted[canonical_id].is_archived is False
    assert persisted[duplicate_id].canonical_item_id == canonical_id
    assert persisted[duplicate_id].is_archived is True
    assert persisted[duplicate_id].archive_reason == "merged_duplicate"


@pytest.mark.asyncio
async def test_keep_separate_decision_keeps_both_items_active_and_independent(
    client: AsyncClient,
    test_user,
    auth_headers,
    db_session: AsyncSession,
):
    first = ClothingItem(
        user_id=test_user.id,
        type="shirt",
        image_path=f"test/{uuid4()}.jpg",
        status=ItemStatus.ready,
    )
    second = ClothingItem(
        user_id=test_user.id,
        type="shirt",
        image_path=f"test/{uuid4()}.jpg",
        status=ItemStatus.ready,
    )
    db_session.add_all([first, second])
    await db_session.flush()
    candidate = DuplicateMatchCandidate(
        user_id=test_user.id,
        item_low_id=min(first.id, second.id),
        item_high_id=max(first.id, second.id),
        status=DuplicateMatchStatus.pending,
        cosine_score=0.88,
        matcher_revision="test-v1",
    )
    db_session.add(candidate)
    await db_session.commit()
    item_ids = [first.id, second.id]

    response = await client.post(
        f"/api/v1/duplicate-matches/{candidate.id}/decision",
        headers=auth_headers,
        json={"decision": "keep_separate"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "kept_separate"
    assert response.json()["canonical_item_id"] is None

    db_session.expire_all()
    items = (
        (await db_session.execute(select(ClothingItem).where(ClothingItem.id.in_(item_ids))))
        .scalars()
        .all()
    )
    assert len(items) == 2
    assert all(item.canonical_item_id is None for item in items)
    assert all(item.is_archived is False for item in items)
