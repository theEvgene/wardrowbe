from io import BytesIO
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from PIL import Image
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.item import ClothingItem, ItemStatus
from app.services.ai_service import ClothingTags
from app.workers import garment_extraction, tagging


def _image_bytes() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (50, 50), (40, 80, 120)).save(buffer, format="JPEG")
    return buffer.getvalue()


class TestUploadAutoExtractionIntent:
    @pytest.mark.asyncio
    async def test_single_upload_defaults_auto_extraction_on(
        self, client: AsyncClient, auth_headers
    ) -> None:
        with patch("app.api.items.create_pool", new_callable=AsyncMock) as create_pool:
            redis = AsyncMock()
            redis.enqueue_job.return_value.job_id = "tag-job"
            create_pool.return_value = redis

            response = await client.post(
                "/api/v1/items",
                files={"image": ("shirt.jpg", _image_bytes(), "image/jpeg")},
                headers=auth_headers,
            )

        assert response.status_code == 201, response.json()
        args, kwargs = redis.enqueue_job.await_args
        assert args[0] == "tag_item_image"
        assert args[3] is True
        assert kwargs == {"_queue_name": "arq:tagging"}

    @pytest.mark.asyncio
    async def test_single_upload_can_disable_auto_extraction(
        self, client: AsyncClient, auth_headers
    ) -> None:
        with patch("app.api.items.create_pool", new_callable=AsyncMock) as create_pool:
            redis = AsyncMock()
            redis.enqueue_job.return_value.job_id = "tag-job"
            create_pool.return_value = redis

            response = await client.post(
                "/api/v1/items",
                files={"image": ("shirt.jpg", _image_bytes(), "image/jpeg")},
                data={"auto_extract": "false"},
                headers=auth_headers,
            )

        assert response.status_code == 201, response.json()
        assert redis.enqueue_job.await_args.args[3] is False

    @pytest.mark.asyncio
    async def test_bulk_upload_propagates_auto_extraction_intent(
        self, client: AsyncClient, auth_headers
    ) -> None:
        with patch("app.api.items.create_pool", new_callable=AsyncMock) as create_pool:
            redis = AsyncMock()
            redis.enqueue_job.return_value.job_id = "tag-job"
            create_pool.return_value = redis

            response = await client.post(
                "/api/v1/items/bulk",
                files=[("images", ("shirt.jpg", _image_bytes(), "image/jpeg"))],
                data={"auto_extract": "false"},
                headers=auth_headers,
            )

        assert response.status_code == 201, response.json()
        assert redis.enqueue_job.await_args.args[3] is False


class TestTaggingExtractionHandoff:
    @pytest.mark.asyncio
    async def test_successful_tagging_queues_requested_extraction(
        self, db_session: AsyncSession, test_user, monkeypatch
    ) -> None:
        item = ClothingItem(
            user_id=test_user.id,
            type="unknown",
            image_path="test/auto-extract.jpg",
            status=ItemStatus.processing,
        )
        db_session.add(item)
        await db_session.commit()

        class StubAI:
            def __init__(self, *args, **kwargs):
                pass

            async def analyze_image(self, path):
                return ClothingTags(type="shirt", primary_color="blue", confidence=0.9)

        settings = tagging.get_settings().model_copy(update={"garment_matching_enabled": False})
        monkeypatch.setattr(tagging, "AIService", StubAI)
        monkeypatch.setattr(tagging, "get_settings", lambda: settings)
        redis = AsyncMock()

        with (
            patch("app.workers.tagging.get_db_session", return_value=db_session),
            patch.object(db_session, "close", new_callable=AsyncMock),
        ):
            result = await tagging.tag_item_image(
                {"redis": redis}, str(item.id), __file__, auto_extract=True
            )

        assert result["status"] == "success"
        redis.enqueue_job.assert_awaited_once_with(
            "extract_item_garment",
            str(item.id),
            _queue_name="arq:tagging",
        )

    @pytest.mark.asyncio
    async def test_successful_tagging_skips_extraction_for_unsupported_type(
        self, db_session: AsyncSession, test_user, monkeypatch
    ) -> None:
        item = ClothingItem(
            user_id=test_user.id,
            type="unknown",
            image_path="test/unsupported-auto-extract.jpg",
            status=ItemStatus.processing,
        )
        db_session.add(item)
        await db_session.commit()

        class StubAI:
            def __init__(self, *args, **kwargs):
                pass

            async def analyze_image(self, path):
                return ClothingTags(type="accessories", primary_color="blue", confidence=0.9)

        settings = tagging.get_settings().model_copy(update={"garment_matching_enabled": False})
        monkeypatch.setattr(tagging, "AIService", StubAI)
        monkeypatch.setattr(tagging, "get_settings", lambda: settings)
        redis = AsyncMock()

        with (
            patch("app.workers.tagging.get_db_session", return_value=db_session),
            patch.object(db_session, "close", new_callable=AsyncMock),
        ):
            result = await tagging.tag_item_image(
                {"redis": redis}, str(item.id), __file__, auto_extract=True
            )

        assert result["status"] == "success"
        redis.enqueue_job.assert_not_awaited()


class TestAutomaticGarmentExtraction:
    @pytest.mark.asyncio
    async def test_accepted_result_is_persisted_and_retry_is_idempotent(
        self, db_session: AsyncSession, test_user, monkeypatch
    ) -> None:
        item = ClothingItem(
            user_id=test_user.id,
            type="shirt",
            image_path="test/idempotent.jpg",
            status=ItemStatus.ready,
        )
        db_session.add(item)
        await db_session.commit()
        await db_session.refresh(item)

        remove_background = AsyncMock(
            return_value={
                "outcome": "accepted",
                "mode": "garment",
                "provider": "test",
                "model": "test-model",
                "garment_category": "upper",
                "transparent_path": "test/idempotent_cutout.png",
                "original_backup_path": "test/idempotent_orig.jpg",
                "metrics": {"duration_ms": 1.0},
            }
        )
        monkeypatch.setattr(garment_extraction, "remove_garment_background", remove_background)

        with (
            patch("app.workers.garment_extraction.get_db_session", return_value=db_session),
            patch.object(db_session, "close", new_callable=AsyncMock),
        ):
            first = await garment_extraction.extract_item_garment({}, str(item.id))
            second = await garment_extraction.extract_item_garment({}, str(item.id))

        assert first["status"] == "accepted"
        assert second == {
            "status": "skipped",
            "reason": "already accepted",
            "item_id": str(item.id),
        }
        assert remove_background.await_count == 1
        await db_session.refresh(item)
        assert item.background_removal["transparent_path"] == "test/idempotent_cutout.png"
        assert item.original_image_path == "test/idempotent_orig.jpg"

    @pytest.mark.asyncio
    async def test_rejected_retry_preserves_existing_accepted_artifact(
        self, db_session: AsyncSession, test_user, monkeypatch
    ) -> None:
        item = ClothingItem(
            user_id=test_user.id,
            type="shirt",
            image_path="test/preserve.jpg",
            status=ItemStatus.ready,
            original_image_path="test/preserve_orig.jpg",
            background_removal={
                "outcome": "accepted",
                "mode": "garment",
                "transparent_path": "test/preserve_cutout.png",
            },
        )
        db_session.add(item)
        await db_session.commit()

        remove_background = AsyncMock()
        monkeypatch.setattr(garment_extraction, "remove_garment_background", remove_background)

        with (
            patch("app.workers.garment_extraction.get_db_session", return_value=db_session),
            patch.object(db_session, "close", new_callable=AsyncMock),
        ):
            result = await garment_extraction.extract_item_garment({}, str(item.id))

        assert result["status"] == "skipped"
        remove_background.assert_not_awaited()
        await db_session.refresh(item)
        assert item.background_removal["transparent_path"] == "test/preserve_cutout.png"
