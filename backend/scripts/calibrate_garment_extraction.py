"""Run the real garment model against the licensed calibration manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from statistics import median
from time import perf_counter
from typing import Any

from PIL import Image

from app.services.background_removal import BackgroundRemovalResult, RembgProvider

DEFAULT_FIXTURE_DIR = Path(__file__).parents[1] / "tests" / "fixtures" / "garment_calibration"


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = round((len(ordered) - 1) * percentile)
    return ordered[index]


def _verify_digest(path: Path, expected: str) -> None:
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != expected:
        raise ValueError(f"SHA-256 mismatch for {path.name}: {actual} != {expected}")


def calibrate(fixture_dir: Path) -> dict[str, Any]:
    manifest = json.loads((fixture_dir / "manifest.json").read_text(encoding="utf-8"))
    provider = RembgProvider()
    samples: list[dict[str, Any]] = []

    # Session creation and model loading are intentionally reported separately:
    # mixing the one-time cold start into a nine-image p95 obscures steady-state
    # inference performance.
    warmup_definition = manifest["samples"][0]
    warmup_path = fixture_dir / warmup_definition["file"]
    _verify_digest(warmup_path, warmup_definition["sha256"])
    cold_started_at = perf_counter()
    provider.remove(
        Image.open(warmup_path).convert("RGB"),
        mode="garment",
        garment_category=warmup_definition["category"],
    )
    cold_start_ms = (perf_counter() - cold_started_at) * 1000

    for definition in manifest["samples"]:
        path = fixture_dir / definition["file"]
        _verify_digest(path, definition["sha256"])
        image = Image.open(path).convert("RGB")
        started_at = perf_counter()
        result = provider.remove(
            image,
            mode="garment",
            garment_category=definition["category"],
        )
        duration_ms = (perf_counter() - started_at) * 1000
        if not isinstance(result, BackgroundRemovalResult):
            raise TypeError(f"Unexpected result for {path.name}: {type(result).__name__}")
        samples.append(
            {
                "file": path.name,
                "category": definition["category"],
                "scenario": definition["scenario"],
                "expected_outcome": definition["expected_outcome"],
                "outcome": result.outcome,
                "matches_baseline": result.outcome == definition["expected_outcome"],
                "duration_ms": round(duration_ms, 2),
                "metrics": {key: round(value, 6) for key, value in result.metrics.items()},
                "warning": result.warning,
            }
        )

    durations = [sample["duration_ms"] for sample in samples]
    outcomes = Counter(sample["outcome"] for sample in samples)
    categories = Counter(sample["category"] for sample in samples)
    return {
        "manifest_version": manifest["version"],
        "model": "u2net_cloth_seg",
        "sample_count": len(samples),
        "baseline_matches": sum(sample["matches_baseline"] for sample in samples),
        "outcomes": dict(sorted(outcomes.items())),
        "categories": dict(sorted(categories.items())),
        "latency_ms": {
            "cold_start": round(cold_start_ms, 2),
            "median": round(median(durations), 2) if durations else None,
            "p95": round(_percentile(durations, 0.95), 2) if durations else None,
            "max": round(max(durations), 2) if durations else None,
        },
        "samples": samples,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURE_DIR)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    report = calibrate(args.fixtures.resolve())
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(f"{rendered}\n", encoding="utf-8")
    print(rendered)
    return int(args.strict and report["baseline_matches"] != report["sample_count"])


if __name__ == "__main__":
    raise SystemExit(main())
