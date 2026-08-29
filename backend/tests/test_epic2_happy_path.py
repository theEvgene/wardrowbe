import json
import re
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.ai_service import ClothingTags
from app.workers import garment_extraction, tagging

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "garment_extraction"


class PromptAwareStyleAI:
    def __init__(self, *args, **kwargs):
        pass

    async def generate_text(self, prompt: str, return_metadata: bool = False):
        count = int(re.search(r"Create exactly (\d+) complete", prompt).group(1))
        matches = re.findall(r"\[(\d+)\] type=([^ |\n]+)", prompt)
        by_type = {
            item_type: [
                int(number) for number, candidate_type in matches if candidate_type == item_type
            ]
            for item_type in {match[1] for match in matches}
        }
        outfits = [
            {
                "items": [
                    by_type["shirt"][index % len(by_type["shirt"])],
                    by_type["pants"][index % len(by_type["pants"])],
                    by_type["shoes"][index % len(by_type["shoes"])],
                ],
                "headline": f"Epic 2 look {index + 1}",
            }
            for index in range(count)
        ]
        return SimpleNamespace(
            content=json.dumps({"outfits": outfits}),
            model="deterministic-epic2",
            endpoint="test",
        )


@pytest.mark.asyncio
async def test_upload_tag_extract_detect_style_and_persist_exact_batch(
    client,
    auth_headers,
    db_session: AsyncSession,
    monkeypatch,
) -> None:
    item_types = ["shirt", "shirt", "pants", "pants", "shoes", "shoes"]
    fixture_names = [
        "worn-person.jpg",
        "worn-upper-occluded.jpg",
        "mannequin.jpg",
        "worn-lower-pants.jpg",
        "hanger.jpg",
        "flat-lay.jpg",
    ]
    upload_redis = AsyncMock()
    upload_redis.enqueue_job.side_effect = lambda *args, **kwargs: SimpleNamespace(
        job_id=f"tag-{args[1]}"
    )

    opened = []
    try:
        files = []
        for name in fixture_names:
            handle = (FIXTURE_DIR / name).open("rb")
            opened.append(handle)
            files.append(("images", (name, handle, "image/jpeg")))
        with patch("app.api.items.create_pool", new_callable=AsyncMock) as create_pool:
            create_pool.return_value = upload_redis
            uploaded = await client.post(
                "/api/v1/items/bulk",
                files=files,
                data={"auto_extract": "true"},
                headers=auth_headers,
            )
    finally:
        for handle in opened:
            handle.close()

    assert uploaded.status_code == 201, uploaded.text
    payload = uploaded.json()
    assert payload["successful"] == 6
    uploaded_items = [row["item"] for row in payload["results"]]
    assert all(call.args[3] is True for call in upload_redis.enqueue_job.await_args_list)

    class TaggingAI:
        current_type = "unknown"

        def __init__(self, *args, **kwargs):
            pass

        async def analyze_image(self, path):
            return ClothingTags(
                type=self.current_type,
                primary_color="blue",
                colors=["blue"],
                style=["casual"],
                confidence=0.95,
            )

    tagging_settings = tagging.get_settings().model_copy(update={"garment_matching_enabled": False})
    monkeypatch.setattr(tagging, "AIService", TaggingAI)
    monkeypatch.setattr(tagging, "get_settings", lambda: tagging_settings)
    worker_redis = AsyncMock()

    with (
        patch("app.workers.tagging.get_db_session", return_value=db_session),
        patch.object(db_session, "close", new_callable=AsyncMock),
    ):
        for item, item_type, enqueue_call in zip(
            uploaded_items, item_types, upload_redis.enqueue_job.await_args_list, strict=True
        ):
            TaggingAI.current_type = item_type
            await tagging.tag_item_image(
                {"redis": worker_redis},
                item["id"],
                enqueue_call.args[2],
                auto_extract=True,
            )

    # The bundled extraction model supports upper/lower garments. Shoes remain
    # usable in outfit generation, but must not be sent through an unsafe mask.
    assert worker_redis.enqueue_job.await_count == 4
    assert all(
        call.args[0] == "extract_item_garment" for call in worker_redis.enqueue_job.await_args_list
    )
    assert {call.args[1] for call in worker_redis.enqueue_job.await_args_list} == {
        item["id"]
        for item, item_type in zip(uploaded_items, item_types, strict=True)
        if item_type in {"shirt", "pants"}
    }

    async def accepted_cutout(image_path: str, item_type: str) -> dict[str, object]:
        stem = image_path.rsplit(".", 1)[0]
        return {
            "outcome": "accepted",
            "mode": "garment",
            "provider": "deterministic-test",
            "model": "test-cutout",
            "garment_category": item_type,
            "transparent_path": f"{stem}_cutout.png",
            "original_backup_path": f"{stem}_orig.jpg",
            "metrics": {"duration_ms": 1.0},
        }

    monkeypatch.setattr(garment_extraction, "remove_garment_background", accepted_cutout)
    with (
        patch("app.workers.garment_extraction.get_db_session", return_value=db_session),
        patch.object(db_session, "close", new_callable=AsyncMock),
    ):
        for item in uploaded_items:
            result = await garment_extraction.extract_item_garment({}, item["id"])
            assert result["status"] == "accepted"

    styles = await client.get("/api/v1/styles/detected", headers=auth_headers)
    assert styles.status_code == 200, styles.text
    assert styles.json() == {"styles": [{"style": "casual", "item_count": 6}]}

    monkeypatch.setattr("app.services.style_outfit_service.AIService", PromptAwareStyleAI)
    generated = await client.post(
        "/api/v1/outfits/generate-by-style",
        json={"target_style": "casual", "count": 2, "occasion": "casual"},
        headers=auth_headers,
    )
    assert generated.status_code == 200, generated.text
    outfits = generated.json()["outfits"]
    assert generated.json()["model"] == "deterministic-epic2"
    assert len(outfits) == 2
    known_ids = {item["id"] for item in uploaded_items}
    for outfit in outfits:
        assert outfit["target_style"] == "casual"
        assert {item["id"] for item in outfit["items"]} <= known_ids
        assert {item["type"] for item in outfit["items"]} == {"shirt", "pants", "shoes"}
        assert all(item["transparent_url"] for item in outfit["items"])
