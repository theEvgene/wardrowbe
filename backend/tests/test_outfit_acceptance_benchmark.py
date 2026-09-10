import json
from pathlib import Path

from scripts.evaluate_outfit_acceptance import evaluate


def test_privacy_safe_benchmark_shows_guardrails_improve_known_failures() -> None:
    fixture = Path(__file__).parent / "fixtures" / "outfit_acceptance" / "cases.json"
    report = evaluate(json.loads(fixture.read_text()))

    assert report["cases"] == 4
    assert report["baseline_accuracy"] == 0.5
    assert report["guardrail_accuracy"] == 1.0
    assert all(detail["guardrail_accept"] == (detail["expected"] == "accept") for detail in report["details"])
