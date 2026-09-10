"""Run the privacy-safe outfit acceptance benchmark."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from types import SimpleNamespace

from app.services.capsule_rules import is_compatible
from app.utils.clothing import ITEM_ROLE


def _item(data: dict) -> SimpleNamespace:
    return SimpleNamespace(
        id=data["id"],
        type=data.get("type"),
        subtype=data.get("subtype"),
        primary_color=data.get("primary_color"),
        colors=data.get("colors", []),
        style=data.get("style", []),
        pattern=data.get("pattern"),
        formality=data.get("formality"),
        season=data.get("season", []),
    )


def _structurally_complete(items: list[SimpleNamespace]) -> bool:
    roles = {ITEM_ROLE.get((item.type or "").lower()) for item in items}
    return "footwear" in roles and ({"base_top", "bottom"} <= roles or "full_body" in roles)


def evaluate(cases: list[dict]) -> dict:
    baseline_correct = 0
    guardrail_correct = 0
    details = []
    for case in cases:
        items = [_item(item) for item in case["items"]]
        baseline = _structurally_complete(items)
        guarded, reason = is_compatible(items, weather_data=case.get("weather"))
        expected = case["expected"] == "accept"
        baseline_correct += baseline == expected
        guardrail_correct += guarded == expected
        details.append(
            {
                "name": case["name"],
                "expected": case["expected"],
                "baseline_accept": baseline,
                "guardrail_accept": guarded,
                "reason": reason,
            }
        )
    total = len(cases)
    return {
        "cases": total,
        "baseline_accuracy": round(baseline_correct / total, 3) if total else 0,
        "guardrail_accuracy": round(guardrail_correct / total, 3) if total else 0,
        "embedding_reranker": "not enabled; evaluated separately after benchmark baseline",
        "details": details,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--fixture",
        type=Path,
        default=Path(__file__).resolve().parents[1]
        / "tests/fixtures/outfit_acceptance/cases.json",
    )
    args = parser.parse_args()
    print(json.dumps(evaluate(json.loads(args.fixture.read_text())), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
