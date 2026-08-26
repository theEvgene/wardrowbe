"""Model-level acceptance tests for garment extraction.

These tests intentionally run the real ONNX model. Set
RUN_GARMENT_MODEL_TESTS=1 in CI or a prepared local environment where rembg
and the u2net_cloth_seg weights are available.
"""

import os
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from app.services.background_removal import (
    BackgroundRemovalResult,
    GarmentCategory,
    RembgProvider,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "garment_extraction"

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_GARMENT_MODEL_TESTS") != "1",
    reason="set RUN_GARMENT_MODEL_TESTS=1 to run the real garment model",
)


def _selected_blue_purity(result: Image.Image) -> float:
    rgba = np.asarray(result.convert("RGBA"))
    foreground = rgba[:, :, 3] > 16
    red = rgba[:, :, 0].astype(float)
    green = rgba[:, :, 1].astype(float)
    blue = rgba[:, :, 2].astype(float)
    selected_blue = (blue > 70) & (blue > red * 1.25) & (blue > green * 1.08)
    return float(selected_blue[foreground].mean())


@pytest.mark.parametrize(
    ("photo_mode", "garment_category", "expected_outcome", "minimum_blue_purity"),
    [
        ("worn-person", "upper", "accepted", 0.90),
        ("mannequin", "upper", "accepted", 0.90),
        ("hanger", "upper", "accepted", 0.85),
        ("flat-lay", "upper", "accepted", 0.85),
        ("worn-upper-occluded", "upper", "low_quality", None),
        ("worn-lower-pants", "lower", "accepted", 0.90),
        ("worn-full-dress", "full", "accepted", 0.90),
    ],
)
def test_real_model_isolates_selected_garment(
    photo_mode: str,
    garment_category: GarmentCategory,
    expected_outcome: str,
    minimum_blue_purity: float | None,
) -> None:
    provider = RembgProvider()
    source = Image.open(FIXTURE_DIR / f"{photo_mode}.jpg").convert("RGB")

    result = provider.remove(
        source,
        mode="garment",
        garment_category=garment_category,
    )

    assert isinstance(result, BackgroundRemovalResult)
    assert result.outcome == expected_outcome
    if expected_outcome == "low_quality":
        assert result.image is None
        assert result.warning
        return

    assert result.image is not None
    assert minimum_blue_purity is not None
    assert _selected_blue_purity(result.image) >= minimum_blue_purity
