"""Anonymous shared operational metrics for garment extraction."""

import json
import logging
from datetime import UTC, datetime
from math import ceil
from typing import Any

from redis.asyncio import Redis

from app.config import get_settings

logger = logging.getLogger(__name__)

WINDOW_CAPACITY = 200
DEFAULT_KEY_PREFIX = "metrics:garment-extraction"
OUTCOMES = ("accepted", "low_quality", "unsupported", "failed")


def _rounded(value: float) -> float:
    return round(value, 3)


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, ceil(percentile * len(ordered)) - 1)
    return ordered[index]


def _optional_float(value: object) -> float | None:
    if isinstance(value, int | float):
        return float(value)
    return None


def _metric_values(samples: list[dict[str, Any]], name: str) -> list[float]:
    return [value for sample in samples if (value := _optional_float(sample.get(name))) is not None]


class GarmentExtractionMetrics:
    """Persist bounded anonymous samples and lifetime counters in shared Redis."""

    def __init__(
        self,
        capacity: int = WINDOW_CAPACITY,
        key_prefix: str = DEFAULT_KEY_PREFIX,
    ) -> None:
        self.capacity = capacity
        self.key_prefix = key_prefix
        self.started_at_key = f"{key_prefix}:started-at"
        self.samples_key = f"{key_prefix}:samples"
        self.outcomes_key = f"{key_prefix}:outcomes"
        self.categories_key = f"{key_prefix}:categories"

    @staticmethod
    def _client() -> Redis:
        return Redis.from_url(str(get_settings().redis_url), decode_responses=True)

    async def record(
        self,
        *,
        outcome: str,
        garment_category: str | None,
        duration_ms: float,
        quality: dict[str, object] | None = None,
    ) -> None:
        quality = quality or {}
        sample = {
            "outcome": outcome,
            "garment_category": garment_category,
            "duration_ms": max(duration_ms, 0.0),
            "mask_area_ratio": _optional_float(quality.get("mask_area_ratio")),
            "largest_component_ratio": _optional_float(quality.get("largest_component_ratio")),
            "semantic_leakage_risk": _optional_float(quality.get("semantic_leakage_risk")),
        }
        redis = self._client()
        try:
            pipe = redis.pipeline(transaction=True)
            pipe.set(self.started_at_key, datetime.now(UTC).isoformat(), nx=True)
            pipe.rpush(self.samples_key, json.dumps(sample, separators=(",", ":")))
            pipe.ltrim(self.samples_key, -self.capacity, -1)
            pipe.hincrby(self.outcomes_key, outcome, 1)
            pipe.hincrby(self.categories_key, garment_category or "unsupported", 1)
            await pipe.execute()
        except Exception:
            logger.warning("Failed to persist garment extraction metrics", exc_info=True)
        finally:
            await redis.aclose()

    async def snapshot(self) -> dict[str, Any]:
        redis = self._client()
        try:
            pipe = redis.pipeline(transaction=False)
            pipe.get(self.started_at_key)
            pipe.lrange(self.samples_key, 0, -1)
            pipe.hgetall(self.outcomes_key)
            pipe.hgetall(self.categories_key)
            started_at, raw_samples, raw_outcomes, raw_categories = await pipe.execute()
        except Exception:
            logger.warning("Failed to read garment extraction metrics", exc_info=True)
            return self._empty_snapshot(available=False)
        finally:
            await redis.aclose()

        samples = []
        for raw_sample in raw_samples:
            try:
                samples.append(json.loads(raw_sample))
            except (TypeError, json.JSONDecodeError):
                logger.warning("Ignoring malformed garment extraction metric sample")
        outcomes = {outcome: int(raw_outcomes.get(outcome, 0)) for outcome in OUTCOMES}
        categories = {key: int(value) for key, value in sorted(raw_categories.items())}
        return self._render_snapshot(
            samples=samples,
            outcomes=outcomes,
            categories=categories,
            started_at=started_at,
            available=True,
        )

    async def clear(self) -> None:
        """Clear this collector's keys; used by isolated integration tests."""

        redis = self._client()
        try:
            await redis.delete(
                self.started_at_key,
                self.samples_key,
                self.outcomes_key,
                self.categories_key,
            )
        finally:
            await redis.aclose()

    def _empty_snapshot(self, *, available: bool) -> dict[str, Any]:
        return self._render_snapshot(
            samples=[],
            outcomes=dict.fromkeys(OUTCOMES, 0),
            categories={},
            started_at=None,
            available=available,
        )

    def _render_snapshot(
        self,
        *,
        samples: list[dict[str, Any]],
        outcomes: dict[str, int],
        categories: dict[str, int],
        started_at: str | None,
        available: bool,
    ) -> dict[str, Any]:
        durations = _metric_values(samples, "duration_ms")
        mask_areas = _metric_values(samples, "mask_area_ratio")
        component_ratios = _metric_values(samples, "largest_component_ratio")
        leakage_risks = _metric_values(samples, "semantic_leakage_risk")
        return {
            "scope": "shared_redis",
            "available": available,
            "started_at": started_at,
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
                "semantic_leakage_samples": len(leakage_risks),
                "average_mask_area_ratio": (
                    _rounded(sum(mask_areas) / len(mask_areas)) if mask_areas else None
                ),
                "average_largest_component_ratio": (
                    _rounded(sum(component_ratios) / len(component_ratios))
                    if component_ratios
                    else None
                ),
                "semantic_leakage_rejection_rate": (
                    _rounded(sum(leakage_risks) / len(leakage_risks)) if leakage_risks else None
                ),
            },
        }


garment_extraction_metrics = GarmentExtractionMetrics()
