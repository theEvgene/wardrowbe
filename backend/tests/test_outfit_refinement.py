import json
import re
from datetime import date
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import create_access_token
from app.models.item import ClothingItem, ItemStatus
from app.models.outfit import Outfit, OutfitItem, OutfitSource, OutfitStatus
from app.models.user import User


class ValidRefinementAI:
    calls = 0

    def __init__(self, *args, **kwargs):
        pass

    async def generate_text(self, prompt: str, return_metadata: bool = False):
        type(self).calls += 1
        matches = re.findall(r"\[(\d+)\] id=[^ ]+ type=([^ ]+) current=(true|false)", prompt)
        by_type = {
            item_type: [
                (int(number), current == "true")
                for number, candidate_type, current in matches
                if candidate_type == item_type
            ]
            for item_type in {match[1] for match in matches}
        }
        alternate_shirt = next(number for number, current in by_type["shirt"] if not current)
        current_pants = next(number for number, current in by_type["pants"] if current)
        current_shoes = next(number for number, current in by_type["shoes"] if current)
        return SimpleNamespace(
            content=json.dumps(
                {
                    "outfit": {
                        "items": [alternate_shirt, current_pants, current_shoes],
                        "headline": "Refined look",
                        "reasoning": "Swapped the top while preserving the requested context.",
                        "styling_tip": "Roll the sleeves once.",
                    }
                }
            ),
            model="gemma3:4b-test",
            endpoint="local-test",
        )


class GuardedRetryAI(ValidRefinementAI):
    calls = 0

    async def generate_text(self, prompt: str, return_metadata: bool = False):
        type(self).calls += 1
        current = [
            int(number)
            for number, is_current in re.findall(r"\[(\d+)\].*?current=(true|false)", prompt)
            if is_current == "true"
        ]
        if type(self).calls == 1:
            content = {"outfit": {"items": current}}
        elif type(self).calls == 2:
            content = {"outfit": {"items": [999]}}
        else:
            type(self).calls -= 1
            return await super().generate_text(prompt, return_metadata=return_metadata)
        return SimpleNamespace(
            content=json.dumps(content),
            model="gemma3:4b-test",
            endpoint="local-test",
        )


class AlwaysInvalidAI:
    calls = 0

    def __init__(self, *args, **kwargs):
        pass

    async def generate_text(self, prompt: str, return_metadata: bool = False):
        type(self).calls += 1
        return SimpleNamespace(
            content=json.dumps({"outfit": {"items": [999]}}),
            model="gemma3:4b-test",
            endpoint="local-test",
        )


async def create_source_outfit(db: AsyncSession, user: User):
    items = [
        ClothingItem(
            user_id=user.id,
            type=item_type,
            name=name,
            image_path=f"test/{uuid4()}.jpg",
            status=ItemStatus.ready,
            style=["casual"],
        )
        for item_type, name in [
            ("shirt", "Original shirt"),
            ("shirt", "Alternate shirt"),
            ("pants", "Pants"),
            ("shoes", "Shoes"),
        ]
    ]
    db.add_all(items)
    await db.flush()
    source = Outfit(
        user_id=user.id,
        occasion="dinner",
        target_style="casual",
        scheduled_for=date(2026, 8, 31),
        weather_data={"condition": "light rain", "temperature": 18},
        generation_context={
            "time_of_day": "evening",
            "activity": "Dinner and a walk",
            "constraints": {"note": "Keep it rain friendly"},
        },
        source=OutfitSource.on_demand,
        status=OutfitStatus.pending,
        name="Original look",
    )
    db.add(source)
    await db.flush()
    original = [items[0], items[2], items[3]]
    for position, item in enumerate(original):
        db.add(OutfitItem(outfit_id=source.id, item_id=item.id, position=position))
    await db.commit()
    return source, items


@pytest.mark.asyncio
async def test_refinement_creates_immutable_successor_and_history(
    client, auth_headers, db_session: AsyncSession, test_user, monkeypatch
) -> None:
    source, items = await create_source_outfit(db_session, test_user)
    ValidRefinementAI.calls = 0
    monkeypatch.setattr("app.services.outfit_refinement_service.AIService", ValidRefinementAI)

    response = await client.post(
        f"/api/v1/outfits/{source.id}/refine",
        json={"instruction": "Use the other shirt and make it more relaxed"},
        headers=auth_headers,
    )

    assert response.status_code == 201, response.json()
    refined = response.json()
    assert refined["id"] != str(source.id)
    assert refined["replaces_outfit_id"] == str(source.id)
    assert refined["weather"] == source.weather_data
    assert refined["scheduled_for"] == source.scheduled_for.isoformat()
    assert refined["target_style"] == source.target_style
    assert refined["occasion"] == source.occasion
    assert refined["generation_context"]["activity"] == "Dinner and a walk"
    assert refined["generation_context"]["refinement"] == {
        "instruction": "Use the other shirt and make it more relaxed",
        "turn": 1,
        "root_outfit_id": str(source.id),
        "parent_outfit_id": str(source.id),
    }
    assert {entry["id"] for entry in refined["items"]} == {
        str(items[1].id),
        str(items[2].id),
        str(items[3].id),
    }

    original = await client.get(f"/api/v1/outfits/{source.id}", headers=auth_headers)
    assert original.status_code == 200
    assert original.json()["replaces_outfit_id"] is None
    assert {entry["id"] for entry in original.json()["items"]} == {
        str(items[0].id),
        str(items[2].id),
        str(items[3].id),
    }

    history = await client.get(
        f"/api/v1/outfits/{refined['id']}/refinement-history", headers=auth_headers
    )
    assert history.status_code == 200, history.json()
    assert [entry["id"] for entry in history.json()["outfits"]] == [
        str(source.id),
        refined["id"],
    ]


@pytest.mark.asyncio
async def test_refinement_supports_multi_turn_from_latest_version(
    client, auth_headers, db_session: AsyncSession, test_user, monkeypatch
) -> None:
    source, _ = await create_source_outfit(db_session, test_user)
    monkeypatch.setattr("app.services.outfit_refinement_service.AIService", ValidRefinementAI)
    first = await client.post(
        f"/api/v1/outfits/{source.id}/refine",
        json={"instruction": "Use the other shirt"},
        headers=auth_headers,
    )
    assert first.status_code == 201, first.json()

    second = await client.post(
        f"/api/v1/outfits/{first.json()['id']}/refine",
        json={"instruction": "Keep it, but make the styling more relaxed"},
        headers=auth_headers,
    )

    assert second.status_code == 201, second.json()
    assert second.json()["replaces_outfit_id"] == first.json()["id"]
    assert second.json()["generation_context"]["refinement"]["turn"] == 2
    assert second.json()["generation_context"]["refinement"]["root_outfit_id"] == str(source.id)


@pytest.mark.asyncio
async def test_refinement_retries_noop_and_hallucinated_item_references(
    client, auth_headers, db_session: AsyncSession, test_user, monkeypatch
) -> None:
    source, _ = await create_source_outfit(db_session, test_user)
    GuardedRetryAI.calls = 0
    monkeypatch.setattr("app.services.outfit_refinement_service.AIService", GuardedRetryAI)

    response = await client.post(
        f"/api/v1/outfits/{source.id}/refine",
        json={"instruction": "Change the shirt"},
        headers=auth_headers,
    )

    assert response.status_code == 201, response.json()
    assert GuardedRetryAI.calls == 3


@pytest.mark.asyncio
async def test_failed_refinement_is_atomic(
    client, auth_headers, db_session: AsyncSession, test_user, monkeypatch
) -> None:
    source, _ = await create_source_outfit(db_session, test_user)
    AlwaysInvalidAI.calls = 0
    monkeypatch.setattr("app.services.outfit_refinement_service.AIService", AlwaysInvalidAI)

    response = await client.post(
        f"/api/v1/outfits/{source.id}/refine",
        json={"instruction": "Invent a completely different outfit"},
        headers=auth_headers,
    )

    assert response.status_code == 503, response.json()
    assert response.json()["detail"]["code"] == "refinement_failed"
    descendants = await db_session.execute(
        select(Outfit).where(Outfit.replaces_outfit_id == source.id)
    )
    assert descendants.scalars().all() == []
    assert AlwaysInvalidAI.calls == 3


@pytest.mark.asyncio
async def test_refinement_hides_another_users_outfit(
    client, db_session: AsyncSession, test_user
) -> None:
    source, _ = await create_source_outfit(db_session, test_user)
    other = User(
        external_id=f"other-{uuid4()}",
        email=f"other-{uuid4()}@example.com",
        display_name="Other User",
        timezone="UTC",
        is_active=True,
    )
    db_session.add(other)
    await db_session.commit()
    headers = {"Authorization": f"Bearer {create_access_token(other.external_id)}"}

    response = await client.post(
        f"/api/v1/outfits/{source.id}/refine",
        json={"instruction": "Change it"},
        headers=headers,
    )

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "outfit_not_found"


@pytest.mark.asyncio
@pytest.mark.parametrize("instruction", ["   ", "x" * 1001])
async def test_refinement_instruction_is_bounded(
    client, auth_headers, db_session: AsyncSession, test_user, instruction
) -> None:
    source, _ = await create_source_outfit(db_session, test_user)

    response = await client.post(
        f"/api/v1/outfits/{source.id}/refine",
        json={"instruction": instruction},
        headers=auth_headers,
    )

    assert response.status_code == 422
