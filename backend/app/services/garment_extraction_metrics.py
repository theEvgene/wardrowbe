"""Anonymous, process-local operational metrics for garment extraction."""

from collections import Counter, deque
from datetime import UTC, datetime
from math import ceil
from threading import Lock
from typing import Any

WINDOW_CAPACITY = 200
OUTCOMES = ("accepted", "low_quality", "unsupported", "failed")


def _rounded(value: float) -> float:
    return round(value, 3)


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, ceil(percentile * len(ordered)) - 1)
    return ordered[index]


class GarmentExtractionMetrics:
    """Keep bounded samples plus lifetime counters without user or image identifiers."""

    def __init__(self, capacity: int = WINDOW_CAPACITY) -> None:
        self.capacity = capacity
        self.started_at = datetime.now(UTC)
        self._lock = Lock()
        self._samples: deque[dict[str, float | str | None]] = deque(maxlen=capacity)
        self._outcomes: Counter[str] = Counter()
        self._categories: Counter[str] = Counter()

    def record(
        self,
        *,
        outcome: str,
        garment_category: str | None,
        duration_ms: float,
        quality: dict[str, object] | None = None,
    ) -> None:
        quality = quality or {}
        sample: dict[str, float | str | None] = {
            "outcome": outcome,
            "garment_category": garment_category,
            "duration_ms": max(duration_ms, 0.0),
            "mask_area_ratio": _optional_float(quality.get("mask_area_ratio")),
            "largest_component_ratio": _optional_float(quality.get("largest_component_ratio")),
        }
        category = garment_category or "unsupported"
        with self._lock:
            self._samples.append(sample)
            self._outcomes[outcome] += 1
            self._categories[category] += 1

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            samples = list(self._samples)
            outcomes = {outcome: self._outcomes[outcome] for outcome in OUTCOMES}
            categories = dict(sorted(self._categories.items()))

        durations = [float(sample["duration_ms"] or 0.0) for sample in samples]
        mask_areas = _metric_values(samples, "mask_area_ratio")
        component_ratios = _metric_values(samples, "largest_component_ratio")
        return {
            "scope": "process",
            "started_at": self.started_at.isoformat(),
            "total_requests": sum(outcomes.values()),
            "window_size": len(samples),
            "window_capacity": self.capacity,
            "outcomes": outcomes,
            "garment_categories": categories,
            "latency_ms": {
                "last": _rounded(durations[-1]) if durations else 0.0,
                "average": _rounded(sum(durations) / len(durations)) if durations else 0.0,
                "p50": _rounded(_percentile(durations, 0.50)),
                "p95": _rounded(_percentile(durations, 0.95)),
            },
            "quality": {
                "samples": len(mask_areas),
                "average_mask_area_ratio": (
                    _rounded(sum(mask_areas) / len(mask_areas)) if mask_areas else None
                ),
                "average_largest_component_ratio": (
                    _rounded(sum(component_ratios) / len(component_ratios))
                    if component_ratios
                    else None
                ),
            },
        }


def _optional_float(value: object) -> float | None:
    if isinstance(value, int | float):
        return float(value)
    return None


def _metric_values(
    samples: list[dict[str, float | str | None]],
    name: str,
) -> list[float]:
    return [float(sample[name]) for sample in samples if sample[name] is not None]


garment_extraction_metrics = GarmentExtractionMetrics()
