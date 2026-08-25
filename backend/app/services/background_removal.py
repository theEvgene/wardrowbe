import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as package_version
from io import BytesIO
from typing import Literal

import httpx
from PIL import Image

from app.config import get_settings
from app.utils.clothing import ITEM_ROLE

logger = logging.getLogger(__name__)

BackgroundRemovalMode = Literal["scene", "garment"]
GarmentCategory = Literal["upper", "lower", "full"]

_GARMENT_CATEGORY_BY_ROLE: dict[str, GarmentCategory] = {
    "base_top": "upper",
    "mid_layer": "upper",
    "outer_layer": "upper",
    "bottom": "lower",
    "full_body": "full",
}


def _installed_package_version(package: str) -> str | None:
    try:
        return package_version(package)
    except PackageNotFoundError:
        return None


def garment_category_for_item_type(item_type: str) -> GarmentCategory | None:
    """Map Wardrowbe's item type to a cloth-segmentation category."""

    role = ITEM_ROLE.get(item_type)
    return _GARMENT_CATEGORY_BY_ROLE.get(role) if role else None


@dataclass(frozen=True)
class BackgroundRemovalResult:
    """Structured result returned by garment-aware background removal."""

    outcome: Literal["accepted", "low_quality", "unsupported"]
    mode: BackgroundRemovalMode
    image: Image.Image | None = None
    provider: str | None = None
    provider_version: str | None = None
    model: str | None = None
    garment_category: GarmentCategory | None = None
    warning: str | None = None
    metrics: dict[str, float] = field(default_factory=dict)


class BackgroundRemovalProvider(ABC):
    @abstractmethod
    def remove(
        self,
        image: Image.Image,
        mode: BackgroundRemovalMode = "scene",
        garment_category: GarmentCategory | None = None,
    ) -> Image.Image | BackgroundRemovalResult:
        """Remove a scene background or return a structured garment result."""


class RembgProvider(BackgroundRemovalProvider):
    def __init__(self, model: str = "u2net"):
        self.model = model
        self._session = None
        self._cloth_session = None

    def _get_session(self):
        if self._session is None:
            from rembg import new_session

            self._session = new_session(self.model)
        return self._session

    def _get_cloth_session(self):
        if self._cloth_session is None:
            from rembg import new_session

            self._cloth_session = new_session("u2net_cloth_seg")
        return self._cloth_session

    def remove(
        self,
        image: Image.Image,
        mode: BackgroundRemovalMode = "scene",
        garment_category: GarmentCategory | None = None,
    ) -> Image.Image | BackgroundRemovalResult:
        from rembg import remove

        if mode == "garment":
            if garment_category is None:
                raise ValueError("Garment category is required for garment extraction")
            result = remove(
                image,
                session=self._get_cloth_session(),
                cloth_category=garment_category,
            )
            result = result.convert("RGBA")
            alpha_histogram = result.getchannel("A").histogram()
            pixel_count = result.width * result.height
            mask_area_ratio = (pixel_count - alpha_histogram[0]) / pixel_count
            metrics = {"mask_area_ratio": mask_area_ratio}
            if mask_area_ratio in (0, 1):
                warning = (
                    "No garment pixels were detected"
                    if mask_area_ratio == 0
                    else "The garment mask covers the full image"
                )
                return BackgroundRemovalResult(
                    outcome="low_quality",
                    mode="garment",
                    provider="rembg",
                    provider_version=_installed_package_version("rembg"),
                    model="u2net_cloth_seg",
                    garment_category=garment_category,
                    warning=warning,
                    metrics=metrics,
                )
            return BackgroundRemovalResult(
                outcome="accepted",
                mode="garment",
                image=result,
                provider="rembg",
                provider_version=_installed_package_version("rembg"),
                model="u2net_cloth_seg",
                garment_category=garment_category,
                metrics=metrics,
            )

        return remove(image, session=self._get_session())


class HttpProvider(BackgroundRemovalProvider):
    def __init__(self, url: str, api_key: str | None = None):
        self.url = url.rstrip("/")
        self.api_key = api_key

    def remove(
        self,
        image: Image.Image,
        mode: BackgroundRemovalMode = "scene",
        garment_category: GarmentCategory | None = None,
    ) -> Image.Image | BackgroundRemovalResult:
        if mode == "garment":
            return BackgroundRemovalResult(
                outcome="unsupported",
                mode=mode,
                provider="http",
                garment_category=garment_category,
                warning="The configured HTTP provider does not support garment extraction",
            )

        buf = BytesIO()
        image.save(buf, format="PNG")
        buf.seek(0)

        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        with httpx.Client(timeout=120, follow_redirects=True) as client:
            response = client.post(
                f"{self.url}/api/remove-background",
                files={"file": ("image.png", buf, "image/png")},
                headers=headers,
            )
            response.raise_for_status()

        return Image.open(BytesIO(response.content)).convert("RGBA")


_provider: BackgroundRemovalProvider | None = None


def get_provider() -> BackgroundRemovalProvider:
    global _provider
    if _provider is not None:
        return _provider

    settings = get_settings()
    provider_type = settings.bg_removal_provider

    if provider_type == "rembg":
        _provider = RembgProvider(model=settings.bg_removal_model)
    elif provider_type == "http":
        if not settings.bg_removal_url:
            raise ValueError("BG_REMOVAL_URL is required when BG_REMOVAL_PROVIDER=http")
        _provider = HttpProvider(url=settings.bg_removal_url, api_key=settings.bg_removal_api_key)
    else:
        raise ValueError(f"Unknown BG_REMOVAL_PROVIDER: {provider_type}. Use 'rembg' or 'http'.")

    return _provider
