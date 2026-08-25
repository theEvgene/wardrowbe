from io import BytesIO
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from httpx import AsyncClient
from PIL import Image
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.item import ClothingItem, ItemStatus
from app.schemas.item import RemoveBackgroundRequest
from app.services.image_service import ImageService


class TestRemoveBackgroundRequest:
    def test_accepts_explicit_garment_mode(self):
        req = RemoveBackgroundRequest(mode="garment")
        assert req.mode == "garment"

    def test_default_white(self):
        req = RemoveBackgroundRequest()
        assert req.bg_color == "#FFFFFF"

    def test_valid_hex(self):
        req = RemoveBackgroundRequest(bg_color="#FF0000")
        assert req.bg_color == "#FF0000"

    def test_lowercase_hex(self):
        req = RemoveBackgroundRequest(bg_color="#aabbcc")
        assert req.bg_color == "#aabbcc"

    def test_rejects_short_hex(self):
        with pytest.raises(ValidationError):
            RemoveBackgroundRequest(bg_color="#FFF")

    def test_rejects_no_hash(self):
        with pytest.raises(ValidationError):
            RemoveBackgroundRequest(bg_color="FFFFFF")

    def test_rejects_invalid_chars(self):
        with pytest.raises(ValidationError):
            RemoveBackgroundRequest(bg_color="#GGGGGG")


class TestRemoveBackgroundEndpoint:
    @pytest.mark.asyncio
    async def test_unsupported_garment_mode_returns_warning_without_backup(
        self,
        client: AsyncClient,
        test_user,
        auth_headers,
        db_session: AsyncSession,
    ):
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

    @pytest.mark.asyncio
    async def test_item_not_found(self, client: AsyncClient, test_user, auth_headers):
        response = await client.post(
            f"/api/v1/items/{uuid4()}/remove-background",
            json={},
            headers=auth_headers,
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_item_no_image(
        self, client: AsyncClient, test_user, auth_headers, db_session: AsyncSession
    ):
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
    async def test_unauthenticated(self, client: AsyncClient):
        response = await client.post(
            f"/api/v1/items/{uuid4()}/remove-background",
            json={},
        )
        assert response.status_code == 401


class TestHealthFeatures:
    @pytest.mark.asyncio
    async def test_features_endpoint(self, client: AsyncClient):
        response = await client.get("/api/v1/health/features")
        assert response.status_code == 200
        data = response.json()
        assert "background_removal" in data
        assert isinstance(data["background_removal"], bool)
