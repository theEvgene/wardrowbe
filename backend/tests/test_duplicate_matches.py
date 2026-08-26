from datetime import UTC, date, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.item import (
    ClothingItem,
    DuplicateMatchCandidate,
    DuplicateMatchStatus,
    ItemHistory,
    ItemImage,
    ItemImageEmbedding,
    ItemStatus,
    TaggedBy,
    WashHistory,
)
from app.schemas.item import ItemFilter
from app.services.garment_identity_service import EmbeddingResult, GarmentIdentityService
from app.services.item_service import ItemService
from app.services.pairing_service import PairingService
from app.services.recommendation_service import RecommendationService
from app.services.weather_service import WeatherData
from app.workers.garment_identity import match_garment_identity


class FakeEmbeddingProvider:
    model = "fake-garment-model"
    model_revision = "test-v1"
    preprocess_revision = "rgb-test-v1"

    def __init__(self, vectors: dict[str, list[float]]):
        self.vectors = vectors

    async def embed(self, image_path: Path) -> EmbeddingResult:
        return EmbeddingResult(vector=self.vectors[image_path.name])


@pytest.mark.asyncio
async def test_pending_match_list_includes_both_review_items(
    client: AsyncClient,
    test_user,
    auth_headers,
    db_session: AsyncSession,
):
    first = ClothingItem(
        user_id=test_user.id,
        type="shorts",
        name="Front view",
        image_path="test/front.jpg",
        status=ItemStatus.ready,
    )
    second = ClothingItem(
        user_id=test_user.id,
        type="shorts",
        name="Back view",
        image_path="test/back.jpg",
        status=ItemStatus.ready,
    )
    db_session.add_all([first, second])
    await db_session.flush()
    candidate = DuplicateMatchCandidate(
        user_id=test_user.id,
        item_low_id=min(first.id, second.id),
        item_high_id=max(first.id, second.id),
        status=DuplicateMatchStatus.pending,
        cosine_score=0.8946,
        matcher_revision="test-v1",
        evidence={"body_role": "lower"},
    )
    db_session.add(candidate)
    await db_session.commit()

    response = await client.get("/api/v1/duplicate-matches", headers=auth_headers)

    assert response.status_code == 200, response.text
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["id"] == str(candidate.id)
    assert {payload[0]["item_low"]["id"], payload[0]["item_high"]["id"]} == {
        str(first.id),
        str(second.id),
    }
    assert payload[0]["item_low"]["image_url"]
    assert payload[0]["item_high"]["image_url"]


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


@pytest.mark.asyncio
async def test_similar_embeddings_create_pending_candidate_without_merging_items(
    test_user,
    db_session: AsyncSession,
):
    first = ClothingItem(
        user_id=test_user.id,
        type="shorts",
        image_path="test/shorts-front.jpg",
        status=ItemStatus.ready,
    )
    second = ClothingItem(
        user_id=test_user.id,
        type="shorts",
        image_path="test/shorts-back.jpg",
        status=ItemStatus.ready,
    )
    db_session.add_all([first, second])
    await db_session.commit()

    provider = FakeEmbeddingProvider(
        {
            "shorts-front.jpg": [1.0, 0.0, 0.0],
            "shorts-back.jpg": [0.99, 0.1, 0.0],
        }
    )
    service = GarmentIdentityService(
        db_session,
        provider=provider,
        review_threshold=0.95,
        storage_root=Path("/tmp"),
    )

    assert await service.analyze_primary_image(first.id, test_user.id) == []
    candidates = await service.analyze_primary_image(second.id, test_user.id)

    assert len(candidates) == 1
    assert candidates[0].status == DuplicateMatchStatus.pending
    assert {candidates[0].item_low_id, candidates[0].item_high_id} == {first.id, second.id}
    item_ids = [first.id, second.id]
    user_id = test_user.id

    db_session.expire_all()
    items = (
        (await db_session.execute(select(ClothingItem).where(ClothingItem.id.in_(item_ids))))
        .scalars()
        .all()
    )
    assert all(item.canonical_item_id is None for item in items)
    assert all(item.is_archived is False for item in items)
    assert (
        (
            await db_session.execute(
                select(ItemImageEmbedding).where(ItemImageEmbedding.user_id == user_id)
            )
        )
        .scalars()
        .all()
    )


@pytest.mark.asyncio
async def test_manual_incompatible_body_roles_veto_visual_match(
    test_user,
    db_session: AsyncSession,
):
    shirt = ClothingItem(
        user_id=test_user.id,
        type="shirt",
        tagged_by=TaggedBy.manual,
        image_path="test/blue-shirt.jpg",
        status=ItemStatus.ready,
    )
    shoes = ClothingItem(
        user_id=test_user.id,
        type="shoes",
        tagged_by=TaggedBy.manual,
        image_path="test/blue-shoes.jpg",
        status=ItemStatus.ready,
    )
    db_session.add_all([shirt, shoes])
    await db_session.commit()

    provider = FakeEmbeddingProvider(
        {
            "blue-shirt.jpg": [1.0, 0.0, 0.0],
            "blue-shoes.jpg": [1.0, 0.0, 0.0],
        }
    )
    service = GarmentIdentityService(
        db_session,
        provider=provider,
        review_threshold=0.95,
        storage_root=Path("/tmp"),
    )

    await service.analyze_primary_image(shirt.id, test_user.id)
    candidates = await service.analyze_primary_image(shoes.id, test_user.id)

    assert candidates == []


@pytest.mark.asyncio
async def test_same_type_hard_negative_below_review_threshold_is_not_proposed(
    test_user,
    db_session: AsyncSession,
):
    first = ClothingItem(
        user_id=test_user.id,
        type="t-shirt",
        image_path="test/distinct-shirt-a.jpg",
        status=ItemStatus.ready,
    )
    second = ClothingItem(
        user_id=test_user.id,
        type="t-shirt",
        image_path="test/distinct-shirt-b.jpg",
        status=ItemStatus.ready,
    )
    db_session.add_all([first, second])
    await db_session.commit()

    provider = FakeEmbeddingProvider(
        {
            "distinct-shirt-a.jpg": [1.0, 0.0],
            "distinct-shirt-b.jpg": [0.849, 0.528392847],
        }
    )
    service = GarmentIdentityService(
        db_session,
        provider=provider,
        review_threshold=0.85,
        storage_root=Path("/tmp"),
    )

    await service.analyze_primary_image(first.id, test_user.id)
    candidates = await service.analyze_primary_image(second.id, test_user.id)

    assert candidates == []


@pytest.mark.asyncio
async def test_worker_job_creates_pending_candidate_with_configured_provider(
    test_user,
    db_session: AsyncSession,
):
    first = ClothingItem(
        user_id=test_user.id,
        type="shorts",
        image_path="test/worker-front.jpg",
        status=ItemStatus.ready,
    )
    second = ClothingItem(
        user_id=test_user.id,
        type="shorts",
        image_path="test/worker-back.jpg",
        status=ItemStatus.ready,
    )
    db_session.add_all([first, second])
    await db_session.commit()

    provider = FakeEmbeddingProvider(
        {
            "worker-front.jpg": [1.0, 0.0, 0.0],
            "worker-back.jpg": [0.99, 0.05, 0.0],
        }
    )
    ctx = {
        "db_session_factory": async_sessionmaker(
            db_session.bind,
            class_=AsyncSession,
            expire_on_commit=False,
        ),
        "garment_embedding_provider": provider,
    }

    first_result = await match_garment_identity(ctx, str(first.id))
    second_result = await match_garment_identity(ctx, str(second.id))

    assert first_result["candidate_ids"] == []
    assert len(second_result["candidate_ids"]) == 1
    candidate = (
        await db_session.execute(
            select(DuplicateMatchCandidate).where(
                DuplicateMatchCandidate.id == second_result["candidate_ids"][0]
            )
        )
    ).scalar_one()
    assert candidate.status == DuplicateMatchStatus.pending


@pytest.mark.asyncio
async def test_recommendation_and_pairing_queries_exclude_alias_even_if_not_archived(
    test_user,
    db_session: AsyncSession,
):
    canonical = ClothingItem(
        user_id=test_user.id,
        type="shirt",
        image_path="test/canonical.jpg",
        status=ItemStatus.ready,
    )
    other = ClothingItem(
        user_id=test_user.id,
        type="pants",
        image_path="test/other.jpg",
        status=ItemStatus.ready,
    )
    db_session.add_all([canonical, other])
    await db_session.flush()
    alias = ClothingItem(
        user_id=test_user.id,
        type="shirt",
        image_path="test/alias.jpg",
        status=ItemStatus.ready,
        canonical_item_id=canonical.id,
        is_archived=False,
    )
    db_session.add(alias)
    await db_session.commit()

    weather = WeatherData(
        temperature=20,
        feels_like=20,
        humidity=50,
        precipitation_chance=0,
        precipitation_mm=0,
        wind_speed=5,
        condition="clear",
        condition_code=0,
        is_day=True,
        uv_index=2,
        timestamp=datetime.now(UTC),
    )
    recommendation_candidates = await RecommendationService(db_session).get_candidate_items(
        user=test_user,
        weather=weather,
        occasion="casual",
        preferences=None,
        exclude_items=[],
    )
    pairing_service = PairingService(db_session)
    pairing_candidates = await pairing_service.get_available_items(test_user, canonical.id)
    item_service = ItemService(db_session)
    listed_items, listed_total = await item_service.get_list(test_user.id, ItemFilter())

    assert {item.id for item in recommendation_candidates} == {canonical.id, other.id}
    assert {item.id for item in pairing_candidates} == {other.id}
    assert await pairing_service.get_source_item(test_user.id, alias.id) is None
    assert await item_service.get_ready_item_count(test_user.id) == 2
    assert listed_total == 2
    assert {item.id for item in listed_items} == {canonical.id, other.id}


@pytest.mark.asyncio
async def test_canonical_item_aggregates_merged_gallery_and_history(
    client: AsyncClient,
    test_user,
    auth_headers,
    db_session: AsyncSession,
):
    canonical = ClothingItem(
        user_id=test_user.id,
        type="shirt",
        image_path="test/canonical-primary.jpg",
        thumbnail_path="test/canonical-primary-thumb.jpg",
        status=ItemStatus.ready,
        wear_count=2,
        last_worn_at=date(2026, 8, 20),
    )
    db_session.add(canonical)
    await db_session.flush()
    alias = ClothingItem(
        user_id=test_user.id,
        type="shirt",
        image_path="test/alias-primary.jpg",
        status=ItemStatus.ready,
        wear_count=3,
        last_worn_at=date(2026, 8, 22),
        canonical_item_id=canonical.id,
        is_archived=True,
        archive_reason="merged_duplicate",
    )
    db_session.add(alias)
    await db_session.flush()
    db_session.add_all(
        [
            ItemImage(
                item_id=canonical.id,
                image_path="test/canonical-additional.jpg",
                position=0,
            ),
            ItemImage(
                item_id=alias.id,
                image_path="test/alias-additional.jpg",
                position=0,
            ),
            ItemHistory(item_id=canonical.id, worn_at=date(2026, 8, 20)),
            ItemHistory(item_id=alias.id, worn_at=date(2026, 8, 22)),
            WashHistory(item_id=canonical.id, washed_at=date(2026, 8, 10)),
            WashHistory(item_id=alias.id, washed_at=date(2026, 8, 21)),
        ]
    )
    await db_session.commit()

    detail_response = await client.get(f"/api/v1/items/{canonical.id}", headers=auth_headers)
    history_response = await client.get(
        f"/api/v1/items/{canonical.id}/history", headers=auth_headers
    )
    wash_response = await client.get(
        f"/api/v1/items/{canonical.id}/wash-history", headers=auth_headers
    )
    stats_response = await client.get(
        f"/api/v1/items/{canonical.id}/wear-stats", headers=auth_headers
    )

    assert detail_response.status_code == 200, detail_response.text
    gallery = detail_response.json()["gallery_images"]
    assert {image["source_item_id"] for image in gallery} == {
        str(canonical.id),
        str(alias.id),
    }
    assert {image["image_path"] for image in gallery} == {
        "test/canonical-primary.jpg",
        "test/canonical-additional.jpg",
        "test/alias-primary.jpg",
        "test/alias-additional.jpg",
    }
    assert history_response.status_code == 200, history_response.text
    assert [entry["worn_at"] for entry in history_response.json()] == [
        "2026-08-22",
        "2026-08-20",
    ]
    assert wash_response.status_code == 200, wash_response.text
    assert [entry["washed_at"] for entry in wash_response.json()] == [
        "2026-08-21",
        "2026-08-10",
    ]
    assert stats_response.status_code == 200, stats_response.text
    assert stats_response.json()["total_wears"] == 5
