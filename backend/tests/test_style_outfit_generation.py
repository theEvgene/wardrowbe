import json
import re
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.outfits import StyleBatchRequest
from app.models.item import ClothingItem, ItemStatus
from app.models.outfit import Outfit
from app.services.recommendation_service import AIRecommendationError
from app.services.style_outfit_service import StyleOutfitService


class TestStyleBatchRequest:
    def test_defaults_to_three_outfits(self) -> None:
        request = StyleBatchRequest(target_style="  Smart-Casual  ")

        assert request.target_style == "smart-casual"
        assert request.count == 3

    @pytest.mark.parametrize("count", [0, 21])
    def test_count_must_be_between_one_and_twenty(self, count: int) -> None:
        with pytest.raises(ValidationError):
            StyleBatchRequest(target_style="casual", count=count)


class PromptAwareAI:
    def __init__(self, *args, **kwargs):
        pass

    async def generate_text(self, prompt: str, return_metadata: bool = False):
        count = int(re.search(r"Create exactly (\d+) complete", prompt).group(1))
        matches = re.findall(r"\[(\d+)\] type=([^ |\n]+)", prompt)
        numbered_types = {
            item_type: [
                int(number) for number, candidate_type in matches if candidate_type == item_type
            ]
            for item_type in {match[1] for match in matches}
        }
        outfits = []
        for index in range(count):
            outfits.append(
                {
                    "items": [
                        numbered_types["shirt"][index % len(numbered_types["shirt"])],
                        numbered_types["pants"][index % len(numbered_types["pants"])],
                        numbered_types["shoes"][index % len(numbered_types["shoes"])],
                    ],
                    "headline": f"Look {index + 1}",
                }
            )
        return SimpleNamespace(
            content=json.dumps({"outfits": outfits}),
            model="test-model",
            endpoint="local-test",
        )


class TestStyleOutfitService:
    @pytest.mark.asyncio
    async def test_public_endpoint_returns_requested_batch(
        self, client, auth_headers, db_session: AsyncSession, test_user, monkeypatch
    ) -> None:
        db_session.add_all(
            [
                ClothingItem(
                    user_id=test_user.id,
                    type=item_type,
                    image_path=f"test/{uuid4()}.jpg",
                    status=ItemStatus.ready,
                    style=["casual"],
                )
                for item_type in ["shirt", "pants", "shoes"]
            ]
        )
        await db_session.commit()
        monkeypatch.setattr("app.services.style_outfit_service.AIService", PromptAwareAI)

        response = await client.post(
            "/api/v1/outfits/generate-by-style",
            json={"target_style": "casual", "count": 1, "occasion": "casual"},
            headers=auth_headers,
        )

        assert response.status_code == 200, response.json()
        assert len(response.json()["outfits"]) == 1
        assert response.json()["outfits"][0]["target_style"] == "casual"

    @pytest.mark.asyncio
    async def test_generates_and_atomically_persists_exactly_n_complete_outfits(
        self, db_session: AsyncSession, test_user, monkeypatch
    ) -> None:
        wardrobe = [
            ClothingItem(
                user_id=test_user.id,
                type=item_type,
                image_path=f"test/{uuid4()}.jpg",
                status=ItemStatus.ready,
                style=["smart-casual"] if item_type == "shirt" else ["casual"],
            )
            for item_type in ["shirt", "shirt", "pants", "pants", "shoes", "shoes"]
        ]
        archived = ClothingItem(
            user_id=test_user.id,
            type="shirt",
            image_path=f"test/{uuid4()}.jpg",
            status=ItemStatus.ready,
            style=["smart-casual"],
            is_archived=True,
        )
        db_session.add_all([*wardrobe, archived])
        await db_session.commit()
        monkeypatch.setattr("app.services.style_outfit_service.AIService", PromptAwareAI)

        outfits = await StyleOutfitService(db_session).generate(
            user=test_user,
            target_style="smart-casual",
            count=2,
            occasion="casual",
        )

        assert len(outfits) == 2
        candidate_ids = {item.id for item in wardrobe}
        key_piece_sets = []
        for outfit in outfits:
            assert outfit.target_style == "smart-casual"
            assert outfit.source_item_id is None
            item_ids = {row.item_id for row in outfit.items}
            assert item_ids <= candidate_ids
            assert archived.id not in item_ids
            types = {row.item.type for row in outfit.items}
            assert {"shirt", "pants", "shoes"} <= types
            key_piece_sets.append(frozenset(item_ids))
        assert len(set(key_piece_sets)) == 2

        persisted = list(
            (
                await db_session.execute(
                    select(Outfit).where(
                        Outfit.user_id == test_user.id,
                        Outfit.target_style == "smart-casual",
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(persisted) == 2

    @pytest.mark.asyncio
    async def test_rejects_a_style_not_detected_in_current_wardrobe(
        self, db_session: AsyncSession, test_user
    ) -> None:
        db_session.add(
            ClothingItem(
                user_id=test_user.id,
                type="shirt",
                image_path=f"test/{uuid4()}.jpg",
                status=ItemStatus.ready,
                style=["casual"],
            )
        )
        await db_session.commit()

        with pytest.raises(ValueError, match="not detected"):
            await StyleOutfitService(db_session).generate(
                user=test_user,
                target_style="formal",
                count=1,
                occasion="casual",
            )


async def _add_generation_wardrobe(db_session: AsyncSession, user_id) -> None:
    db_session.add_all(
        [
            ClothingItem(
                user_id=user_id,
                type=item_type,
                image_path=f"test/{uuid4()}.jpg",
                status=ItemStatus.ready,
                style=["casual"],
            )
            for item_type in ["shirt", "shirt", "pants", "pants", "shoes", "shoes"]
        ]
    )
    await db_session.commit()


class TestAdversarialStyleGeneration:
    @pytest.mark.asyncio
    async def test_recovers_on_a_bounded_follow_up_attempt(
        self, db_session: AsyncSession, test_user, monkeypatch
    ) -> None:
        await _add_generation_wardrobe(db_session, test_user.id)

        class RecoveringAI(PromptAwareAI):
            calls = 0

            async def generate_text(self, prompt: str, return_metadata: bool = False):
                type(self).calls += 1
                if type(self).calls == 1:
                    return SimpleNamespace(
                        content='{"outfits":[', model="test", endpoint="local-test"
                    )
                return await super().generate_text(prompt, return_metadata)

        monkeypatch.setattr("app.services.style_outfit_service.AIService", RecoveringAI)

        outfits = await StyleOutfitService(db_session).generate(
            user=test_user,
            target_style="casual",
            count=2,
            occasion="casual",
        )

        assert len(outfits) == 2
        assert RecoveringAI.calls == 2

    @pytest.mark.parametrize(
        "response_kind",
        ["malformed", "truncated", "unknown-id", "incomplete", "duplicate-sets", "unsafe-copy"],
    )
    @pytest.mark.asyncio
    async def test_rejects_adversarial_responses_without_partial_persistence(
        self, response_kind: str, db_session: AsyncSession, test_user, monkeypatch
    ) -> None:
        await _add_generation_wardrobe(db_session, test_user.id)

        class AdversarialAI:
            calls = 0

            def __init__(self, *args, **kwargs):
                pass

            async def generate_text(self, prompt: str, return_metadata: bool = False):
                type(self).calls += 1
                matches = re.findall(r"\[(\d+)\] type=([^ |\n]+)", prompt)
                by_type = {
                    item_type: [
                        int(number)
                        for number, candidate_type in matches
                        if candidate_type == item_type
                    ]
                    for item_type in {match[1] for match in matches}
                }
                valid = [by_type["shirt"][0], by_type["pants"][0], by_type["shoes"][0]]
                content_by_kind = {
                    "malformed": "not json",
                    "truncated": '{"outfits":[',
                    "unknown-id": json.dumps({"outfits": [{"items": [999, *valid[1:]]}]}),
                    "incomplete": json.dumps(
                        {"outfits": [{"items": [by_type["shirt"][0], by_type["shoes"][0]]}]}
                    ),
                    "duplicate-sets": json.dumps({"outfits": [{"items": valid}, {"items": valid}]}),
                    "unsafe-copy": json.dumps(
                        {"outfits": [{"items": valid, "headline": "x" * 2500}]}
                    ),
                }
                return SimpleNamespace(
                    content=content_by_kind[response_kind],
                    model="test",
                    endpoint="local-test",
                )

        monkeypatch.setattr("app.services.style_outfit_service.AIService", AdversarialAI)

        with pytest.raises(AIRecommendationError, match="after 3 attempts"):
            await StyleOutfitService(db_session).generate(
                user=test_user,
                target_style="casual",
                count=2,
                occasion="casual",
            )

        assert AdversarialAI.calls == 3
        persisted = list(
            (
                await db_session.execute(
                    select(Outfit).where(
                        Outfit.user_id == test_user.id,
                        Outfit.target_style == "casual",
                    )
                )
            )
            .scalars()
            .all()
        )
        assert persisted == []
