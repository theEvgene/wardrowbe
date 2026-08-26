import json
from datetime import date
from types import SimpleNamespace
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import create_access_token
from app.models.family import Family
from app.models.item import ClothingItem, ItemStatus
from app.models.outfit import (
    FamilyOutfitRating,
    Outfit,
    OutfitItem,
    OutfitSource,
    OutfitStatus,
)
from app.models.user import User
from app.services import pairing_service as pairing_module
from app.services.pairing_service import PairingService


def _make_item(user_id, item_type="shirt", **kwargs) -> ClothingItem:
    return ClothingItem(
        user_id=user_id,
        type=item_type,
        image_path=f"test/{uuid4()}.jpg",
        status=ItemStatus.ready,
        **kwargs,
    )


def _make_pairing(user_id, items: list[ClothingItem], source_item=None) -> Outfit:
    outfit = Outfit(
        user_id=user_id,
        occasion="casual",
        scheduled_for=date.today(),
        status=OutfitStatus.pending,
        source=OutfitSource.pairing,
        source_item_id=source_item.id if source_item else None,
        reasoning="Test pairing",
    )
    for i, item in enumerate(items):
        outfit_item = OutfitItem(
            item_id=item.id,
            position=i,
        )
        outfit.items.append(outfit_item)
    return outfit


async def _generate_with_ai_payload(
    monkeypatch,
    db_session: AsyncSession,
    test_user,
    source: ClothingItem,
    available: list[ClothingItem],
    payload: dict,
) -> Outfit:
    class StubAIService:
        def __init__(self, *args, **kwargs):
            pass

        async def generate_text(self, prompt, return_metadata=False):
            return SimpleNamespace(content=json.dumps([payload]), model="test-model")

    monkeypatch.setattr(pairing_module, "require_internal_ai", lambda _capability: None)
    monkeypatch.setattr(pairing_module, "AIService", StubAIService)
    test_user.preferences = None
    db_session.add_all([source, *available])
    await db_session.flush()

    outfits = await PairingService(db_session).generate_pairings(test_user, source.id, 1)
    assert len(outfits) == 1
    return outfits[0]


class TestPairingCopyValidation:
    @pytest.mark.asyncio
    async def test_valid_structured_copy_is_preserved(
        self, monkeypatch, db_session: AsyncSession, test_user
    ):
        source = _make_item(test_user.id, "shirt", primary_color="white")
        pants = _make_item(test_user.id, "pants", primary_color="navy", pattern="solid")
        shoes = _make_item(test_user.id, "shoes", primary_color="brown")
        outfit = await _generate_with_ai_payload(
            monkeypatch,
            db_session,
            test_user,
            source,
            [pants, shoes],
            {
                "items": [1, 2, 3],
                "headline": {"text": "White shirt with navy pants", "items": [1, 2]},
                "highlights": [
                    {"text": "Brown shoes finish the outfit", "items": [3]},
                ],
                "styling_tip": {"text": "Keep the white shirt crisp", "items": [1]},
            },
        )

        assert outfit.reasoning == "White shirt with navy pants"
        assert outfit.style_notes == "Keep the white shirt crisp"
        assert outfit.ai_raw_response["highlights"] == ["Brown shoes finish the outfit"]
        assert outfit.ai_raw_response["validation"] == {
            "valid": True,
            "fallback": None,
            "errors": [],
        }

    @pytest.mark.asyncio
    async def test_structured_claim_with_wrong_item_metadata_uses_fallback(
        self, monkeypatch, db_session: AsyncSession, test_user
    ):
        source = _make_item(test_user.id, "shirt", primary_color="white")
        pants = _make_item(test_user.id, "pants", primary_color="navy")
        shoes = _make_item(test_user.id, "shoes", primary_color="brown")
        outfit = await _generate_with_ai_payload(
            monkeypatch,
            db_session,
            test_user,
            source,
            [pants, shoes],
            {
                "items": [1, 2, 3],
                "headline": {"text": "Simple outfit", "items": [1, 2, 3]},
                "highlights": [
                    {"text": "The red graphic shirt adds contrast", "items": [2]},
                ],
                "styling_tip": {"text": "Wear together", "items": [1, 2, 3]},
            },
        )

        visible_copy = " ".join(
            [outfit.reasoning or "", outfit.style_notes or ""]
            + outfit.ai_raw_response["highlights"]
        ).lower()
        assert "red" not in visible_copy
        assert (
            "metadata_mismatch:highlights[0]:red" in outfit.ai_raw_response["validation"]["errors"]
        )
        assert (
            "metadata_mismatch:highlights[0]:shirt"
            in outfit.ai_raw_response["validation"]["errors"]
        )
        assert (
            "metadata_mismatch:highlights[0]:graphic"
            in outfit.ai_raw_response["validation"]["errors"]
        )

    @pytest.mark.asyncio
    async def test_phantom_garment_prose_falls_back_to_selected_item_metadata(
        self, monkeypatch, db_session: AsyncSession, test_user
    ):
        source = _make_item(
            test_user.id,
            "t-shirt",
            name="Beige floral tee",
            primary_color="beige",
            pattern="floral",
        )
        shorts = _make_item(test_user.id, "shorts", primary_color="blue")
        shoes = _make_item(test_user.id, "shoes", primary_color="white")
        outfit = await _generate_with_ai_payload(
            monkeypatch,
            db_session,
            test_user,
            source,
            [shorts, shoes],
            {
                "items": [1, 2, 3],
                "headline": "Red graphic tee look",
                "highlights": ["Add a black T-shirt for contrast"],
                "styling_tip": "Let the red top lead",
            },
        )

        visible_copy = " ".join(
            [outfit.reasoning or "", outfit.style_notes or ""]
            + outfit.ai_raw_response["highlights"]
        ).lower()
        assert "red" not in visible_copy
        assert "black" not in visible_copy
        assert outfit.ai_raw_response["validation"]["fallback"] == "deterministic"
        assert outfit.ai_raw_response["raw_ai_output"]["headline"] == "Red graphic tee look"

    @pytest.mark.asyncio
    async def test_invalid_item_number_cannot_reach_visible_copy(
        self, monkeypatch, db_session: AsyncSession, test_user
    ):
        source = _make_item(test_user.id, "shirt", primary_color="white")
        pants = _make_item(test_user.id, "pants", primary_color="navy")
        shoes = _make_item(test_user.id, "shoes", primary_color="brown")
        outfit = await _generate_with_ai_payload(
            monkeypatch,
            db_session,
            test_user,
            source,
            [pants, shoes],
            {
                "items": [1, 2, 99],
                "headline": "Item 99 finishes it",
                "highlights": ["Item 99 adds a jacket"],
                "styling_tip": "Layer item 99",
            },
        )

        visible_copy = " ".join(
            [outfit.reasoning or "", outfit.style_notes or ""]
            + outfit.ai_raw_response["highlights"]
        ).lower()
        assert "99" not in visible_copy
        assert "jacket" not in visible_copy
        assert "invalid_item_number:99" in outfit.ai_raw_response["validation"]["errors"]

    @pytest.mark.asyncio
    async def test_copy_is_rewritten_after_body_slot_deduplication(
        self, monkeypatch, db_session: AsyncSession, test_user
    ):
        source = _make_item(test_user.id, "t-shirt", primary_color="beige")
        shorts = _make_item(test_user.id, "shorts", primary_color="blue")
        pants = _make_item(test_user.id, "pants", primary_color="black")
        shoes = _make_item(test_user.id, "shoes", primary_color="white")
        outfit = await _generate_with_ai_payload(
            monkeypatch,
            db_session,
            test_user,
            source,
            [shorts, pants, shoes],
            {
                "items": [1, 2, 3, 4],
                "headline": "Black pants anchor",
                "highlights": ["Item 3 black pants balance the tee"],
                "styling_tip": "Cuff the black pants",
            },
        )

        persisted_item_ids = {outfit_item.item_id for outfit_item in outfit.items}
        assert persisted_item_ids == {source.id, shorts.id, shoes.id}
        visible_copy = " ".join(
            [outfit.reasoning or "", outfit.style_notes or ""]
            + outfit.ai_raw_response["highlights"]
        ).lower()
        assert "black" not in visible_copy
        assert "pants" not in visible_copy
        assert "removed_by_body_slot:3" in outfit.ai_raw_response["validation"]["errors"]


@pytest.fixture
def second_user_factory():
    def _make(family_id=None):
        uid = uuid4()
        return User(
            id=uid,
            external_id=f"test-user-{uid}",
            email=f"test-{uid}@example.com",
            display_name="Second User",
            timezone="UTC",
            is_active=True,
            onboarding_completed=False,
            family_id=family_id,
        )

    return _make


class TestListPairings:
    @pytest.mark.asyncio
    async def test_list_pairings_empty(self, client: AsyncClient, test_user, auth_headers):
        response = await client.get("/api/v1/pairings", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["pairings"] == []
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_list_pairings_returns_data(
        self, client: AsyncClient, test_user, auth_headers, db_session: AsyncSession
    ):
        item1 = _make_item(test_user.id, "shirt")
        item2 = _make_item(test_user.id, "pants")
        db_session.add_all([item1, item2])
        await db_session.flush()

        pairing = _make_pairing(test_user.id, [item1, item2], source_item=item1)
        db_session.add(pairing)
        await db_session.commit()

        response = await client.get("/api/v1/pairings", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["pairings"]) == 1
        assert data["pairings"][0]["source"] == "pairing"
        assert len(data["pairings"][0]["items"]) == 2


class TestPairingResponseIncludesFamilyRatings:
    @pytest.mark.asyncio
    async def test_pairing_response_has_family_rating_fields(
        self, client: AsyncClient, test_user, auth_headers, db_session: AsyncSession
    ):
        item = _make_item(test_user.id)
        db_session.add(item)
        await db_session.flush()

        pairing = _make_pairing(test_user.id, [item])
        db_session.add(pairing)
        await db_session.commit()

        response = await client.get("/api/v1/pairings", headers=auth_headers)
        data = response.json()
        p = data["pairings"][0]
        assert "family_ratings" in p
        assert "family_rating_average" in p
        assert "family_rating_count" in p

    @pytest.mark.asyncio
    async def test_pairing_with_family_rating_returns_data(
        self, client: AsyncClient, test_user, auth_headers, db_session: AsyncSession
    ):
        family = Family(
            name="Test Family", invite_code=f"TST{uuid4().hex[:6]}", created_by=test_user.id
        )
        db_session.add(family)
        await db_session.flush()

        test_user.family_id = family.id
        await db_session.flush()

        rater = User(
            id=uuid4(),
            external_id=f"rater-{uuid4()}",
            email=f"rater-{uuid4()}@example.com",
            display_name="Rater",
            timezone="UTC",
            is_active=True,
            family_id=family.id,
        )
        db_session.add(rater)
        await db_session.flush()

        item = _make_item(test_user.id)
        db_session.add(item)
        await db_session.flush()

        pairing = _make_pairing(test_user.id, [item])
        db_session.add(pairing)
        await db_session.flush()

        rating = FamilyOutfitRating(
            outfit_id=pairing.id,
            user_id=rater.id,
            rating=4,
            comment="Nice combo!",
        )
        db_session.add(rating)
        await db_session.commit()

        response = await client.get("/api/v1/pairings", headers=auth_headers)
        data = response.json()
        p = data["pairings"][0]
        assert p["family_rating_count"] == 1
        assert p["family_rating_average"] == 4.0
        assert len(p["family_ratings"]) == 1
        assert p["family_ratings"][0]["rating"] == 4
        assert p["family_ratings"][0]["comment"] == "Nice combo!"
        assert p["family_ratings"][0]["user_display_name"] == "Rater"

    @pytest.mark.asyncio
    async def test_pairing_without_ratings_returns_null(
        self, client: AsyncClient, test_user, auth_headers, db_session: AsyncSession
    ):
        item = _make_item(test_user.id)
        db_session.add(item)
        await db_session.flush()

        pairing = _make_pairing(test_user.id, [item])
        db_session.add(pairing)
        await db_session.commit()

        response = await client.get("/api/v1/pairings", headers=auth_headers)
        data = response.json()
        p = data["pairings"][0]
        assert p["family_ratings"] is None
        assert p["family_rating_average"] is None
        assert p["family_rating_count"] is None


class TestFamilyRatingEndpoint:
    @pytest.mark.asyncio
    async def test_cannot_rate_own_outfit(
        self, client: AsyncClient, test_user, auth_headers, db_session: AsyncSession
    ):
        family = Family(
            name="Test Family", invite_code=f"FAM{uuid4().hex[:6]}", created_by=test_user.id
        )
        db_session.add(family)
        await db_session.flush()

        test_user.family_id = family.id
        await db_session.flush()

        item = _make_item(test_user.id)
        db_session.add(item)
        await db_session.flush()

        pairing = _make_pairing(test_user.id, [item])
        db_session.add(pairing)
        await db_session.commit()

        response = await client.post(
            f"/api/v1/outfits/{pairing.id}/family-rating",
            json={"rating": 5},
            headers=auth_headers,
        )
        assert response.status_code == 400
        assert "Cannot rate your own" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_family_member_can_rate(
        self, client: AsyncClient, test_user, db_session: AsyncSession
    ):
        family = Family(
            name="Test Family", invite_code=f"FAM{uuid4().hex[:6]}", created_by=test_user.id
        )
        db_session.add(family)
        await db_session.flush()

        test_user.family_id = family.id

        rater = User(
            id=uuid4(),
            external_id=f"rater-{uuid4()}",
            email=f"rater-{uuid4()}@example.com",
            display_name="Family Rater",
            timezone="UTC",
            is_active=True,
            family_id=family.id,
        )
        db_session.add(rater)
        await db_session.flush()

        item = _make_item(test_user.id)
        db_session.add(item)
        await db_session.flush()

        pairing = _make_pairing(test_user.id, [item])
        db_session.add(pairing)
        await db_session.commit()

        rater_token = create_access_token(rater.external_id)
        rater_headers = {"Authorization": f"Bearer {rater_token}"}

        response = await client.post(
            f"/api/v1/outfits/{pairing.id}/family-rating",
            json={"rating": 4, "comment": "Looks great!"},
            headers=rater_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["rating"] == 4
        assert data["comment"] == "Looks great!"

    @pytest.mark.asyncio
    async def test_non_family_member_cannot_rate(
        self, client: AsyncClient, test_user, db_session: AsyncSession
    ):
        item = _make_item(test_user.id)
        db_session.add(item)
        await db_session.flush()

        pairing = _make_pairing(test_user.id, [item])
        db_session.add(pairing)

        outsider = User(
            id=uuid4(),
            external_id=f"outsider-{uuid4()}",
            email=f"outsider-{uuid4()}@example.com",
            display_name="Outsider",
            timezone="UTC",
            is_active=True,
        )
        db_session.add(outsider)
        await db_session.commit()

        outsider_token = create_access_token(outsider.external_id)
        outsider_headers = {"Authorization": f"Bearer {outsider_token}"}

        response = await client.post(
            f"/api/v1/outfits/{pairing.id}/family-rating",
            json={"rating": 3},
            headers=outsider_headers,
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_rating_upsert(self, client: AsyncClient, test_user, db_session: AsyncSession):
        family = Family(
            name="Test Family", invite_code=f"FAM{uuid4().hex[:6]}", created_by=test_user.id
        )
        db_session.add(family)
        await db_session.flush()

        test_user.family_id = family.id

        rater = User(
            id=uuid4(),
            external_id=f"rater-{uuid4()}",
            email=f"rater-{uuid4()}@example.com",
            display_name="Rater",
            timezone="UTC",
            is_active=True,
            family_id=family.id,
        )
        db_session.add(rater)
        await db_session.flush()

        item = _make_item(test_user.id)
        db_session.add(item)
        await db_session.flush()

        pairing = _make_pairing(test_user.id, [item])
        db_session.add(pairing)
        await db_session.commit()

        rater_token = create_access_token(rater.external_id)
        rater_headers = {"Authorization": f"Bearer {rater_token}"}

        # First rating
        response = await client.post(
            f"/api/v1/outfits/{pairing.id}/family-rating",
            json={"rating": 3},
            headers=rater_headers,
        )
        assert response.status_code == 200
        assert response.json()["rating"] == 3

        # Update (upsert)
        response = await client.post(
            f"/api/v1/outfits/{pairing.id}/family-rating",
            json={"rating": 5, "comment": "Changed my mind!"},
            headers=rater_headers,
        )
        assert response.status_code == 200
        assert response.json()["rating"] == 5
        assert response.json()["comment"] == "Changed my mind!"


class TestDeletePairing:
    @pytest.mark.asyncio
    async def test_delete_own_pairing(
        self, client: AsyncClient, test_user, auth_headers, db_session: AsyncSession
    ):
        item = _make_item(test_user.id)
        db_session.add(item)
        await db_session.flush()

        pairing = _make_pairing(test_user.id, [item])
        db_session.add(pairing)
        await db_session.commit()

        response = await client.delete(f"/api/v1/pairings/{pairing.id}", headers=auth_headers)
        assert response.status_code == 204

        # Verify deleted
        response = await client.get("/api/v1/pairings", headers=auth_headers)
        assert response.json()["total"] == 0

    @pytest.mark.asyncio
    async def test_cannot_delete_other_users_pairing(
        self, client: AsyncClient, test_user, auth_headers, db_session: AsyncSession
    ):
        other_user = User(
            id=uuid4(),
            external_id=f"other-{uuid4()}",
            email=f"other-{uuid4()}@example.com",
            display_name="Other",
            timezone="UTC",
            is_active=True,
        )
        db_session.add(other_user)
        await db_session.flush()

        item = _make_item(other_user.id)
        db_session.add(item)
        await db_session.flush()

        pairing = _make_pairing(other_user.id, [item])
        db_session.add(pairing)
        await db_session.commit()

        response = await client.delete(f"/api/v1/pairings/{pairing.id}", headers=auth_headers)
        assert response.status_code == 404
