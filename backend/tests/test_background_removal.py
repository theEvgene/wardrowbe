from io import BytesIO
from pathlib import Path
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


def _make_rgba_image(w: int = 100, h: int = 100) -> Image.Image:
    return Image.new("RGBA", (w, h), (255, 0, 0, 128))


def _make_rgb_image(w: int = 100, h: int = 100) -> Image.Image:
    return Image.new("RGB", (w, h), (200, 150, 100))


def _make_garment_cutout(w: int = 100, h: int = 100) -> Image.Image:
    image = Image.new("RGBA", (w, h), (255, 0, 0, 0))
    image.paste((255, 0, 0, 255), (20, 20, 80, 80))
    return image


def _garment_result_for_mask(mask: Image.Image) -> BackgroundRemovalResult:
    provider = RembgProvider(model="u2net")
    with patch.dict(
        "sys.modules",
        {
            "rembg": MagicMock(
                new_session=MagicMock(return_value="cloth-session"),
                remove=MagicMock(return_value=mask),
            )
        },
    ):
        result = provider.remove(
            _make_rgb_image(),
            mode="garment",
            garment_category="upper",
        )
    assert isinstance(result, BackgroundRemovalResult)
    return result


def test_shirt_maps_to_upper_garment_category() -> None:
    assert garment_category_for_item_type("shirt") == "upper"


def test_unsupported_garment_type_does_not_change_image(tmp_path: Path) -> None:
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


def test_low_quality_garment_result_does_not_change_image(tmp_path: Path) -> None:
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


def test_provider_failure_does_not_change_image(tmp_path: Path) -> None:
    image_path = tmp_path / "item.jpg"
    _make_rgb_image().save(image_path, format="JPEG")
    original_bytes = image_path.read_bytes()
    svc = ImageService(storage_path=str(tmp_path))
    provider = MagicMock(spec=BackgroundRemovalProvider)
    provider.remove.side_effect = RuntimeError("model crashed")

    with patch("app.services.background_removal.get_provider", return_value=provider):
        result = svc.remove_background("item.jpg", mode="garment", item_type="shirt")

    assert result["outcome"] == "failed"
    assert "model crashed" in str(result["warning"])
    assert image_path.read_bytes() == original_bytes
    assert not (tmp_path / "item_orig.jpg").exists()


def test_scene_removal_preserves_existing_provider_contract(tmp_path: Path) -> None:
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


def test_garment_removal_preserves_transparent_cutout(tmp_path: Path) -> None:
    image_path = tmp_path / "item.jpg"
    _make_rgb_image().save(image_path, format="JPEG")
    svc = ImageService(storage_path=str(tmp_path))
    provider = MagicMock(spec=BackgroundRemovalProvider)
    provider.remove.return_value = BackgroundRemovalResult(
        outcome="accepted",
        mode="garment",
        image=_make_garment_cutout(),
        provider="rembg",
        provider_version="2.0.81",
        model="u2net_cloth_seg",
        garment_category="upper",
        metrics={"mask_area_ratio": 0.36},
    )

    with patch("app.services.background_removal.get_provider", return_value=provider):
        result = svc.remove_background("item.jpg", mode="garment", item_type="shirt")

    assert result["transparent_path"] == "item_cutout.png"
    cutout = Image.open(tmp_path / "item_cutout.png")
    assert cutout.mode == "RGBA"
    assert cutout.getpixel((0, 0))[3] == 0
    assert cutout.getpixel((50, 50))[3] == 255

    svc.restore_original("item.jpg", str(result["original_backup_path"]))

    assert not (tmp_path / "item_cutout.png").exists()


class TestRembgProvider:
    def test_fragmented_garment_mask_returns_low_quality_result(self) -> None:
        fragmented_mask = Image.new("RGBA", (100, 100), (255, 0, 0, 0))
        fragmented_mask.paste((255, 0, 0, 255), (10, 10, 40, 40))
        fragmented_mask.paste((255, 0, 0, 255), (60, 60, 90, 90))

        result = _garment_result_for_mask(fragmented_mask)

        assert result.outcome == "low_quality"
        assert result.image is None
        assert result.metrics["largest_component_ratio"] == 0.5

    def test_tiny_garment_mask_returns_low_quality_result(self) -> None:
        tiny_mask = Image.new("RGBA", (100, 100), (255, 0, 0, 0))
        tiny_mask.paste((255, 0, 0, 255), (0, 0, 5, 10))

        result = _garment_result_for_mask(tiny_mask)

        assert result.outcome == "low_quality"
        assert result.image is None
        assert result.metrics["mask_area_ratio"] == 0.005

    def test_full_frame_garment_mask_returns_low_quality_result(self) -> None:
        full_frame_mask = Image.new("RGBA", (100, 100), (255, 0, 0, 255))

        result = _garment_result_for_mask(full_frame_mask)

        assert result.outcome == "low_quality"
        assert result.image is None
        assert result.metrics["mask_area_ratio"] == 1.0

    def test_empty_garment_mask_returns_low_quality_result(self) -> None:
        empty_mask = Image.new("RGBA", (100, 100), (255, 0, 0, 0))

        result = _garment_result_for_mask(empty_mask)

        assert result.outcome == "low_quality"
        assert result.image is None
        assert result.metrics["mask_area_ratio"] == 0.0

    def test_garment_extraction_returns_selected_clothing_category(self) -> None:
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

    def test_remove_calls_rembg(self) -> None:
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
        assert isinstance(result, BackgroundRemovalResult)
        assert result.outcome == "accepted"
        assert result.mode == "scene"
        assert result.provider == "rembg"
        assert result.model == "u2net"
        assert result.image is mock_result

    def test_session_is_cached(self) -> None:
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

    def test_custom_model(self) -> None:
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
    def test_garment_mode_is_unsupported_without_http_request(self) -> None:
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

    def test_remove_posts_to_url(self) -> None:
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
        assert isinstance(result, BackgroundRemovalResult)
        assert result.outcome == "accepted"
        assert result.mode == "scene"
        assert result.provider == "http"
        assert result.image is not None
        assert result.image.mode == "RGBA"

    def test_strips_trailing_slash(self) -> None:
        provider = HttpProvider(url="http://bg-service:5000/")
        assert provider.url == "http://bg-service:5000"

    def test_auth_header_when_api_key_set(self) -> None:
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

    def test_rembg_provider(self) -> None:
        settings = MagicMock()
        settings.bg_removal_provider = "rembg"
        settings.bg_removal_model = "u2net"
        with patch("app.services.background_removal.get_settings", return_value=settings):
            provider = get_provider()
        assert isinstance(provider, RembgProvider)
        assert provider.model == "u2net"

    def test_http_provider(self) -> None:
        settings = MagicMock()
        settings.bg_removal_provider = "http"
        settings.bg_removal_url = "http://withoutbg:5000"
        settings.bg_removal_api_key = "key123"
        with patch("app.services.background_removal.get_settings", return_value=settings):
            provider = get_provider()
        assert isinstance(provider, HttpProvider)
        assert provider.url == "http://withoutbg:5000"
        assert provider.api_key == "key123"

    def test_http_provider_requires_url(self) -> None:
        settings = MagicMock()
        settings.bg_removal_provider = "http"
        settings.bg_removal_url = None
        with (
            patch("app.services.background_removal.get_settings", return_value=settings),
            pytest.raises(ValueError, match="BG_REMOVAL_URL is required"),
        ):
            get_provider()

    def test_unknown_provider_raises(self) -> None:
        settings = MagicMock()
        settings.bg_removal_provider = "magic"
        with (
            patch("app.services.background_removal.get_settings", return_value=settings),
            pytest.raises(ValueError, match="Unknown BG_REMOVAL_PROVIDER"),
        ):
            get_provider()

    def test_provider_is_cached(self) -> None:
        settings = MagicMock()
        settings.bg_removal_provider = "rembg"
        settings.bg_removal_model = "u2net"
        with patch("app.services.background_removal.get_settings", return_value=settings):
            p1 = get_provider()
            p2 = get_provider()
        assert p1 is p2

    def test_is_abstract(self) -> None:
        with pytest.raises(TypeError):
            BackgroundRemovalProvider()
