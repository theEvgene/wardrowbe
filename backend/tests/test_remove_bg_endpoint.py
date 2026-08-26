from io import BytesIO
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from httpx import AsyncClient
from PIL import Image
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.item import ClothingItem, ItemStatus
from app.models.user import User
from app.schemas.item import RemoveBackgroundRequest
from app.services.background_removal import BackgroundRemovalResult
from app.services.image_service import ImageService


class TestRemoveBackgroundRequest:
    def test_accepts_explicit_garment_mode(self) -> None:
        req = RemoveBackgroundRequest(mode="garment")
        assert req.mode == "garment"

    def test_default_white(self) -> None:
        req = RemoveBackgroundRequest()
        assert req.bg_color == "#FFFFFF"

    def test_valid_hex(self) -> None:
        req = RemoveBackgroundRequest(bg_color="#FF0000")
        assert req.bg_color == "#FF0000"

    def test_lowercase_hex(self) -> None:
        req = RemoveBackgroundRequest(bg_color="#aabbcc")
        assert req.bg_color == "#aabbcc"

    def test_rejects_short_hex(self) -> None:
        with pytest.raises(ValidationError):
            RemoveBackgroundRequest(bg_color="#FFF")

    def test_rejects_no_hash(self) -> None:
        with pytest.raises(ValidationError):
            RemoveBackgroundRequest(bg_color="FFFFFF")

    def test_rejects_invalid_chars(self) -> None:
        with pytest.raises(ValidationError):
            RemoveBackgroundRequest(bg_color="#GGGGGG")


class TestRemoveBackgroundEndpoint:
    @pytest.mark.asyncio
    async def test_unsupported_garment_mode_returns_warning_without_backup(
        self,
        client: AsyncClient,
        test_user: User,
        auth_headers: dict[str, str],
        db_session: AsyncSession,
    ) -> None:
        before_response = await client.get("/api/v1/health/metrics/garment-extraction")
        assert before_response.status_code == 200
        before = before_response.json()

        image_bytes = BytesIO()
        Image.new("RGB", (100, 100), (30, 60, 90)).save(image_bytes, format="JPEG")
        paths = await ImageService().process_and_store(
            test_user.id,
            image_bytes.getvalue(),
            "shoes.jpg",
        )
        item = ClothingItem(
            user_id=test_user.id,
            type="shoes",
            image_path=paths["image_path"],
            medium_path=paths["medium_path"],
            thumbnail_path=paths["thumbnail_path"],
            image_hash=paths["image_hash"],
            status=ItemStatus.ready,
        )
        db_session.add(item)
        await db_session.commit()
        await db_session.refresh(item)
        provider = MagicMock()
        provider.remove.return_value = Image.new("RGBA", (100, 100), (255, 0, 0, 255))

        with patch("app.services.background_removal.get_provider", return_value=provider):
            response = await client.post(
                f"/api/v1/items/{item.id}/remove-background",
                json={"mode": "garment"},
                headers=auth_headers,
            )

        assert response.status_code == 200
        data = response.json()
        assert data["background_removal"]["outcome"] == "unsupported"
        assert data["original_image_path"] is None

        persisted = await client.get(f"/api/v1/items/{item.id}", headers=auth_headers)
        assert persisted.status_code == 200
        assert persisted.json()["background_removal"]["outcome"] == "unsupported"

        after_response = await client.get("/api/v1/health/metrics/garment-extraction")
        assert after_response.status_code == 200
        after = after_response.json()
        assert after["total_requests"] == before["total_requests"] + 1
        assert after["outcomes"]["unsupported"] == before["outcomes"]["unsupported"] + 1
        assert after["latency_ms"]["last"] >= 0
        assert after["window_size"] <= after["window_capacity"]
        assert "item_id" not in after
        assert "user_id" not in after

    @pytest.mark.asyncio
    async def test_accepted_garment_updates_latency_and_quality_metrics(
        self,
        client: AsyncClient,
        test_user: User,
        auth_headers: dict[str, str],
        db_session: AsyncSession,
    ) -> None:
        before = (await client.get("/api/v1/health/metrics/garment-extraction")).json()
        image_bytes = BytesIO()
        Image.new("RGB", (100, 100), (30, 60, 90)).save(image_bytes, format="JPEG")
        paths = await ImageService().process_and_store(
            test_user.id,
            image_bytes.getvalue(),
            "shirt.jpg",
        )
        item = ClothingItem(
            user_id=test_user.id,
            type="shirt",
            image_path=paths["image_path"],
            medium_path=paths["medium_path"],
            thumbnail_path=paths["thumbnail_path"],
            image_hash=paths["image_hash"],
            status=ItemStatus.ready,
        )
        db_session.add(item)
        await db_session.commit()
        await db_session.refresh(item)
        provider = MagicMock()
        provider.remove.return_value = BackgroundRemovalResult(
            outcome="accepted",
            mode="garment",
            image=Image.new("RGBA", (100, 100), (255, 0, 0, 255)),
            provider="rembg",
            model="u2net_cloth_seg",
            garment_category="upper",
            metrics={"mask_area_ratio": 0.4, "largest_component_ratio": 0.95},
        )

        with patch("app.services.background_removal.get_provider", return_value=provider):
            response = await client.post(
                f"/api/v1/items/{item.id}/remove-background",
                json={"mode": "garment"},
                headers=auth_headers,
            )

        assert response.status_code == 200
        request_metrics = response.json()["background_removal"]["metrics"]
        assert request_metrics["duration_ms"] >= 0
        after = (await client.get("/api/v1/health/metrics/garment-extraction")).json()
        assert after["total_requests"] == before["total_requests"] + 1
        assert after["outcomes"]["accepted"] == before["outcomes"]["accepted"] + 1
        assert after["garment_categories"]["upper"] == (
            before["garment_categories"].get("upper", 0) + 1
        )
        assert after["quality"]["samples"] == before["quality"]["samples"] + 1
        assert after["quality"]["average_mask_area_ratio"] is not None

    @pytest.mark.asyncio
    async def test_rejected_retry_preserves_active_background_state(
        self,
        client: AsyncClient,
        test_user: User,
        auth_headers: dict[str, str],
        db_session: AsyncSession,
    ) -> None:
        image_bytes = BytesIO()
        Image.new("RGB", (100, 100), (30, 60, 90)).save(image_bytes, format="JPEG")
        paths = await ImageService().process_and_store(
            test_user.id,
            image_bytes.getvalue(),
            "shoes.jpg",
        )
        active_state = {
            "outcome": "accepted",
            "mode": "garment",
            "provider": "rembg",
            "model": "u2net_cloth_seg",
            "transparent_path": f"{test_user.id}/active_cutout.png",
            "metrics": {"mask_area_ratio": 0.25},
        }
        item = ClothingItem(
            user_id=test_user.id,
            type="shoes",
            image_path=paths["image_path"],
            medium_path=paths["medium_path"],
            thumbnail_path=paths["thumbnail_path"],
            image_hash=paths["image_hash"],
            background_removal=active_state,
            status=ItemStatus.ready,
        )
        db_session.add(item)
        await db_session.commit()
        await db_session.refresh(item)

        response = await client.post(
            f"/api/v1/items/{item.id}/remove-background",
            json={"mode": "garment"},
            headers=auth_headers,
        )

        assert response.status_code == 200
        assert response.json()["background_removal"]["outcome"] == "unsupported"
        persisted = await client.get(f"/api/v1/items/{item.id}", headers=auth_headers)
        persisted_state = persisted.json()["background_removal"]
        assert persisted_state["outcome"] == "accepted"
        assert persisted_state["transparent_path"] == active_state["transparent_path"]

    @pytest.mark.asyncio
    async def test_item_not_found(
        self,
        client: AsyncClient,
        test_user: User,
        auth_headers: dict[str, str],
    ) -> None:
        response = await client.post(
            f"/api/v1/items/{uuid4()}/remove-background",
            json={},
            headers=auth_headers,
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_item_no_image(
        self,
        client: AsyncClient,
        test_user: User,
        auth_headers: dict[str, str],
        db_session: AsyncSession,
    ) -> None:
        item = ClothingItem(
            user_id=test_user.id,
            type="shirt",
            image_path="",
            status=ItemStatus.ready,
        )
        db_session.add(item)
        await db_session.commit()
        await db_session.refresh(item)

        response = await client.post(
            f"/api/v1/items/{item.id}/remove-background",
            json={},
            headers=auth_headers,
        )
        assert response.status_code == 400
        assert "no image" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_unauthenticated(self, client: AsyncClient) -> None:
        response = await client.post(
            f"/api/v1/items/{uuid4()}/remove-background",
            json={},
        )
        assert response.status_code == 401


class TestHealthFeatures:
    @pytest.mark.asyncio
    async def test_features_endpoint(self, client: AsyncClient) -> None:
        response = await client.get("/api/v1/health/features")
        assert response.status_code == 200
        data = response.json()
        assert "background_removal" in data
        assert isinstance(data["background_removal"], bool)
