from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from app.services.background_removal import (
    BackgroundRemovalProvider,
    BackgroundRemovalResult,
    HttpProvider,
    RembgProvider,
    garment_category_for_item_type,
    get_provider,
)
from app.services.image_service import ImageService


def _make_rgba_image(w=100, h=100):
    return Image.new("RGBA", (w, h), (255, 0, 0, 128))


def _make_rgb_image(w=100, h=100):
    return Image.new("RGB", (w, h), (200, 150, 100))


def _make_garment_cutout(w=100, h=100):
    image = Image.new("RGBA", (w, h), (255, 0, 0, 0))
    image.paste((255, 0, 0, 255), (20, 20, 80, 80))
    return image


def test_shirt_maps_to_upper_garment_category():
    assert garment_category_for_item_type("shirt") == "upper"


def test_unsupported_garment_type_does_not_change_image(tmp_path):
    image_path = tmp_path / "item.jpg"
    _make_rgb_image().save(image_path, format="JPEG")
    original_bytes = image_path.read_bytes()
    svc = ImageService(storage_path=str(tmp_path))

    result = svc.remove_background(
        "item.jpg",
        mode="garment",
        item_type="shoes",
    )

    assert result["outcome"] == "unsupported"
    assert image_path.read_bytes() == original_bytes
    assert not (tmp_path / "item_orig.jpg").exists()


def test_low_quality_garment_result_does_not_change_image(tmp_path):
    image_path = tmp_path / "item.jpg"
    _make_rgb_image().save(image_path, format="JPEG")
    original_bytes = image_path.read_bytes()
    svc = ImageService(storage_path=str(tmp_path))
    provider = MagicMock(spec=BackgroundRemovalProvider)
    provider.remove.return_value = BackgroundRemovalResult(
        outcome="low_quality",
        mode="garment",
        model="u2net_cloth_seg",
        garment_category="upper",
        warning="No garment pixels were detected",
        metrics={"mask_area_ratio": 0.0},
    )

    with patch("app.services.background_removal.get_provider", return_value=provider):
        result = svc.remove_background(
            "item.jpg",
            mode="garment",
            item_type="shirt",
        )

    assert result["outcome"] == "low_quality"
    assert image_path.read_bytes() == original_bytes
    assert not (tmp_path / "item_orig.jpg").exists()


def test_scene_removal_preserves_existing_provider_contract(tmp_path):
    image_path = tmp_path / "item.jpg"
    _make_rgb_image().save(image_path, format="JPEG")
    svc = ImageService(storage_path=str(tmp_path))
    provider = MagicMock(spec=BackgroundRemovalProvider)
    provider.remove.side_effect = lambda image: _make_rgba_image(*image.size)

    with patch("app.services.background_removal.get_provider", return_value=provider):
        result = svc.remove_background("item.jpg")

    assert result["outcome"] == "accepted"
    assert result["original_backup_path"] == "item_orig.jpg"
    assert (tmp_path / "item_orig.jpg").exists()


class TestRembgProvider:
    def test_full_frame_garment_mask_returns_low_quality_result(self):
        provider = RembgProvider(model="u2net")
        full_frame_mask = Image.new("RGBA", (100, 100), (255, 0, 0, 255))
        mock_new_session = MagicMock(return_value="cloth-session")
        mock_remove = MagicMock(return_value=full_frame_mask)
        with patch.dict(
            "sys.modules",
            {"rembg": MagicMock(new_session=mock_new_session, remove=mock_remove)},
        ):
            result = provider.remove(
                _make_rgb_image(),
                mode="garment",
                garment_category="upper",
            )

        assert result.outcome == "low_quality"
        assert result.image is None
        assert result.metrics["mask_area_ratio"] == 1.0

    def test_empty_garment_mask_returns_low_quality_result(self):
        provider = RembgProvider(model="u2net")
        empty_mask = Image.new("RGBA", (100, 100), (255, 0, 0, 0))
        mock_new_session = MagicMock(return_value="cloth-session")
        mock_remove = MagicMock(return_value=empty_mask)
        with patch.dict(
            "sys.modules",
            {"rembg": MagicMock(new_session=mock_new_session, remove=mock_remove)},
        ):
            result = provider.remove(
                _make_rgb_image(),
                mode="garment",
                garment_category="upper",
            )

        assert result.outcome == "low_quality"
        assert result.image is None
        assert result.metrics["mask_area_ratio"] == 0.0

    def test_garment_extraction_returns_selected_clothing_category(self):
        provider = RembgProvider(model="u2net")
        mock_result = _make_garment_cutout()
        mock_new_session = MagicMock(return_value="cloth-session")
        mock_remove = MagicMock(return_value=mock_result)
        with patch.dict(
            "sys.modules",
            {"rembg": MagicMock(new_session=mock_new_session, remove=mock_remove)},
        ):
            result = provider.remove(
                _make_rgb_image(),
                mode="garment",
                garment_category="upper",
            )

        mock_new_session.assert_called_once_with("u2net_cloth_seg")
        assert mock_remove.call_args.kwargs["cloth_category"] == "upper"
        assert result.outcome == "accepted"
        assert result.provider == "rembg"
        assert result.image.mode == "RGBA"

    def test_remove_calls_rembg(self):
        provider = RembgProvider(model="u2net")
        mock_result = _make_rgba_image()
        mock_new_session = MagicMock(return_value="fake-session")
        mock_remove = MagicMock(return_value=mock_result)
        with (
            patch.dict(
                "sys.modules",
                {"rembg": MagicMock(new_session=mock_new_session, remove=mock_remove)},
            ),
        ):
            result = provider.remove(_make_rgb_image())

        mock_new_session.assert_called_once_with("u2net")
        mock_remove.assert_called_once()
        assert result.mode == "RGBA"

    def test_session_is_cached(self):
        provider = RembgProvider(model="u2net")
        mock_result = _make_rgba_image()
        mock_new_session = MagicMock(return_value="fake-session")
        mock_remove = MagicMock(return_value=mock_result)
        with (
            patch.dict(
                "sys.modules",
                {"rembg": MagicMock(new_session=mock_new_session, remove=mock_remove)},
            ),
        ):
            provider.remove(_make_rgb_image())
            provider.remove(_make_rgb_image())

        mock_new_session.assert_called_once()

    def test_custom_model(self):
        provider = RembgProvider(model="isnet-general-use")
        mock_result = _make_rgba_image()
        mock_new_session = MagicMock(return_value="fake-session")
        mock_remove = MagicMock(return_value=mock_result)
        with (
            patch.dict(
                "sys.modules",
                {"rembg": MagicMock(new_session=mock_new_session, remove=mock_remove)},
            ),
        ):
            provider.remove(_make_rgb_image())

        mock_new_session.assert_called_once_with("isnet-general-use")


class TestHttpProvider:
    def test_garment_mode_is_unsupported_without_http_request(self):
        provider = HttpProvider(url="http://bg-service:5000")

        with patch("app.services.background_removal.httpx.Client") as mock_client:
            result = provider.remove(
                _make_rgb_image(),
                mode="garment",
                garment_category="upper",
            )

        assert result.outcome == "unsupported"
        assert result.image is None
        mock_client.assert_not_called()

    def test_remove_posts_to_url(self):
        provider = HttpProvider(url="http://bg-service:5000", api_key="test-key")
        png_bytes = BytesIO()
        _make_rgba_image().save(png_bytes, format="PNG")
        png_bytes.seek(0)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = png_bytes.getvalue()
        mock_response.raise_for_status = MagicMock()

        with patch("app.services.background_removal.httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = mock_response
            mock_client_cls.return_value = mock_client

            result = provider.remove(_make_rgb_image())

        mock_client.post.assert_called_once()
        call_kwargs = mock_client.post.call_args
        assert "http://bg-service:5000/api/remove-background" in call_kwargs.args
        assert result.mode == "RGBA"

    def test_strips_trailing_slash(self):
        provider = HttpProvider(url="http://bg-service:5000/")
        assert provider.url == "http://bg-service:5000"

    def test_auth_header_when_api_key_set(self):
        provider = HttpProvider(url="http://bg-service:5000", api_key="my-key")
        png_bytes = BytesIO()
        _make_rgba_image().save(png_bytes, format="PNG")

        mock_response = MagicMock()
        mock_response.content = png_bytes.getvalue()
        mock_response.raise_for_status = MagicMock()

        with patch("app.services.background_removal.httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = mock_response
            mock_client_cls.return_value = mock_client

            provider.remove(_make_rgb_image())

        call_kwargs = mock_client.post.call_args
        assert call_kwargs.kwargs["headers"]["Authorization"] == "Bearer my-key"


class TestGetProvider:
    def setup_method(self):
        import app.services.background_removal as mod

        mod._provider = None

    def test_rembg_provider(self):
        settings = MagicMock()
        settings.bg_removal_provider = "rembg"
        settings.bg_removal_model = "u2net"
        with patch("app.services.background_removal.get_settings", return_value=settings):
            provider = get_provider()
        assert isinstance(provider, RembgProvider)
        assert provider.model == "u2net"

    def test_http_provider(self):
        settings = MagicMock()
        settings.bg_removal_provider = "http"
        settings.bg_removal_url = "http://withoutbg:5000"
        settings.bg_removal_api_key = "key123"
        with patch("app.services.background_removal.get_settings", return_value=settings):
            provider = get_provider()
        assert isinstance(provider, HttpProvider)
        assert provider.url == "http://withoutbg:5000"
        assert provider.api_key == "key123"

    def test_http_provider_requires_url(self):
        settings = MagicMock()
        settings.bg_removal_provider = "http"
        settings.bg_removal_url = None
        with (
            patch("app.services.background_removal.get_settings", return_value=settings),
            pytest.raises(ValueError, match="BG_REMOVAL_URL is required"),
        ):
            get_provider()

    def test_unknown_provider_raises(self):
        settings = MagicMock()
        settings.bg_removal_provider = "magic"
        with (
            patch("app.services.background_removal.get_settings", return_value=settings),
            pytest.raises(ValueError, match="Unknown BG_REMOVAL_PROVIDER"),
        ):
            get_provider()

    def test_provider_is_cached(self):
        settings = MagicMock()
        settings.bg_removal_provider = "rembg"
        settings.bg_removal_model = "u2net"
        with patch("app.services.background_removal.get_settings", return_value=settings):
            p1 = get_provider()
            p2 = get_provider()
        assert p1 is p2

    def test_is_abstract(self):
        with pytest.raises(TypeError):
            BackgroundRemovalProvider()
