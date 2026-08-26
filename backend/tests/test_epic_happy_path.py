"""End-to-end happy path for epic #1 across public HTTP and worker seams."""

import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api import items as items_api
from app.services import pairing_service as pairing_module
from app.services.garment_identity_service import EmbeddingResult
from app.workers.garment_identity import match_garment_identity

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "garment_extraction"

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_EPIC_E2E") != "1",
    reason="set RUN_EPIC_E2E=1 to run the real epic happy path",
)


class HappyPathEmbeddingProvider:
    model = "happy-path-garment-model"
    model_revision = "e2e-v1"
    preprocess_revision = "e2e-v1"

    def __init__(self, same_garment_names: set[str]):
        self.same_garment_names = same_garment_names

    async def embed(self, image_path: Path) -> EmbeddingResult:
        if image_path.name in self.same_garment_names:
            return EmbeddingResult(vector=[1.0, 0.0, 0.0])
        return EmbeddingResult(vector=[0.0, 1.0, 0.0])


class HappyPathAIService:
    def __init__(self, *args, **kwargs):
        pass

    async def generate_text(self, prompt, return_metadata=False):
        payload = [
            {
                "items": [1, 2, 3],
                "headline": {
                    "text": "Blue shirt with beige pants and white shoes",
                    "items": [1, 2, 3],
                },
                "highlights": [
                    {"text": "White shoes finish the outfit", "items": [3]},
                ],
                "styling_tip": {
                    "text": "Keep the blue shirt untucked",
                    "items": [1],
                },
            }
        ]
        return SimpleNamespace(content=json.dumps(payload), model="happy-path-ai")


async def _confirm_metadata(
    client: AsyncClient,
    headers: dict[str, str],
    item_id: str,
    *,
    item_type: str,
    primary_color: str,
) -> dict:
    response = await client.patch(
        f"/api/v1/items/{item_id}",
        headers=headers,
        json={
            "type": item_type,
            "primary_color": primary_color,
            "colors": [primary_color],
            "confirm_fields": ["type", "primary_color", "colors"],
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["field_metadata"]["type"]["provenance"] == "user_confirmed"
    assert payload["field_metadata"]["primary_color"]["provenance"] == "user_confirmed"
    return payload


@pytest.mark.asyncio
async def test_epic_happy_path_from_upload_to_composite_pairing(
    client: AsyncClient,
    test_user,
    auth_headers: dict[str, str],
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Keep upload deterministic; the identity worker is invoked explicitly at
    # its queue boundary below instead of racing a live Redis worker.
    monkeypatch.setattr(items_api.settings, "garment_matching_enabled", False)

    onboarding = await client.post(
        "/api/v1/users/me/onboarding/complete",
        headers=auth_headers,
    )
    assert onboarding.status_code == 200, onboarding.text
    assert onboarding.json()["onboarding_completed"] is True

    with (FIXTURE_DIR / "worn-person.jpg").open("rb") as source_file:
        single = await client.post(
            "/api/v1/items",
            headers=auth_headers,
            data={"type": "shirt", "skip_ai": "true"},
            files={"image": ("worn-person.jpg", source_file, "image/jpeg")},
        )
    assert single.status_code == 201, single.text
    source = single.json()

    bulk_files = []
    opened_files = []
    try:
        for fixture_name in ["mannequin.jpg", "hanger.jpg", "flat-lay.jpg"]:
            fixture = (FIXTURE_DIR / fixture_name).open("rb")
            opened_files.append(fixture)
            bulk_files.append(("images", (fixture_name, fixture, "image/jpeg")))
        bulk = await client.post(
            "/api/v1/items/bulk",
            headers=auth_headers,
            data={"skip_ai": "true"},
            files=bulk_files,
        )
    finally:
        for fixture in opened_files:
            fixture.close()

    assert bulk.status_code == 201, bulk.text
    bulk_payload = bulk.json()
    assert bulk_payload["successful"] == 3
    uploaded = [result["item"] for result in bulk_payload["results"]]
    same_shirt, trousers, shoes = uploaded

    source = await _confirm_metadata(
        client, auth_headers, source["id"], item_type="shirt", primary_color="blue"
    )
    same_shirt = await _confirm_metadata(
        client, auth_headers, same_shirt["id"], item_type="shirt", primary_color="blue"
    )
    trousers = await _confirm_metadata(
        client, auth_headers, trousers["id"], item_type="pants", primary_color="beige"
    )
    shoes = await _confirm_metadata(
        client, auth_headers, shoes["id"], item_type="shoes", primary_color="white"
    )

    extracted = await client.post(
        f"/api/v1/items/{source['id']}/remove-background",
        headers=auth_headers,
        json={"mode": "garment"},
    )
    assert extracted.status_code == 200, extracted.text
    assert extracted.json()["background_removal"]["outcome"] == "accepted"
    assert extracted.json()["background_removal"]["transparent_path"]

    monkeypatch.setattr(items_api.settings, "garment_matching_enabled", True)
    provider = HappyPathEmbeddingProvider(
        {Path(source["image_path"]).name, Path(same_shirt["image_path"]).name}
    )
    worker_context = {
        "db_session_factory": async_sessionmaker(
            db_session.bind,
            class_=AsyncSession,
            expire_on_commit=False,
        ),
        "garment_embedding_provider": provider,
    }
    first_match = await match_garment_identity(worker_context, source["id"])
    second_match = await match_garment_identity(worker_context, same_shirt["id"])
    assert first_match["candidate_ids"] == []
    assert len(second_match["candidate_ids"]) == 1

    pending = await client.get("/api/v1/duplicate-matches", headers=auth_headers)
    assert pending.status_code == 200, pending.text
    assert len(pending.json()) == 1
    decision = await client.post(
        f"/api/v1/duplicate-matches/{pending.json()[0]['id']}/decision",
        headers=auth_headers,
        json={"decision": "merge", "canonical_item_id": source["id"]},
    )
    assert decision.status_code == 200, decision.text
    assert decision.json()["status"] == "merged"

    monkeypatch.setattr(pairing_module, "require_internal_ai", lambda _capability: None)
    monkeypatch.setattr(pairing_module, "AIService", HappyPathAIService)
    generated = await client.post(
        f"/api/v1/pairings/generate/{source['id']}",
        headers=auth_headers,
        json={"num_pairings": 1},
    )
    assert generated.status_code == 200, generated.text
    payload = generated.json()
    assert payload["generated"] == 1
    pairing = payload["pairings"][0]
    assert {item["id"] for item in pairing["items"]} == {
        source["id"],
        trousers["id"],
        shoes["id"],
    }
    assert same_shirt["id"] not in {item["id"] for item in pairing["items"]}
    assert pairing["reasoning"] == "Blue shirt with beige pants and white shoes"
    source_preview = next(item for item in pairing["items"] if item["id"] == source["id"])
    assert source_preview["transparent_url"]

    outfit = await client.get(f"/api/v1/outfits/{pairing['id']}", headers=auth_headers)
    assert outfit.status_code == 200, outfit.text
    assert len(outfit.json()["items"]) == 3
