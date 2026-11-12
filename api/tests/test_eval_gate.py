"""The nightly regression gate: a 2 p.p. drop fails, noise does not, and the budget holds."""

import json
from pathlib import Path
from typing import Any

from evals.gate import compare, main, over_budget, pick_run, run_label


def _run(label: str = "fake", **summary: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "vitals": {"value_accuracy": 0.90, "recall": 0.95, "precision": 0.9},
        "patient_match_accuracy": 0.98,
        "alert_accuracy": 1.0,
        "symptoms": {"f1": 0.8},
        "medications": {"f1": 0.7},
        "cost_usd": {"total": 0.5, "per_note": 0.004},
    }
    for key, value in summary.items():
        if isinstance(value, dict):
            base[key] = {**base[key], **value}
        else:
            base[key] = value
    return {
        "config": {
            "provider": label,
            "model": "m",
            "mode": "text",
            "dataset": "evals/data/cases_holdout.jsonl",
        },
        "summary": base,
    }


def test_a_drop_beyond_the_threshold_fails_and_noise_does_not() -> None:
    findings = compare(
        _run(), _run(vitals={"value_accuracy": 0.87}, patient_match_accuracy=0.97), 0.02
    )
    by_name = {f.metric: f for f in findings}
    assert by_name["vitals.value_accuracy"].failed  # -3 p.p.
    assert not by_name["patient_match_accuracy"].failed  # -1 p.p.
    assert not by_name["alert_accuracy"].failed  # unchanged
    assert "FAIL" in str(by_name["vitals.value_accuracy"])


def test_missing_metrics_are_not_regressions() -> None:
    findings = compare(_run(symptoms={"f1": None}), _run(symptoms={"f1": 0.5}), 0.02)
    assert not next(f for f in findings if f.metric == "symptoms.f1").failed


def test_budget() -> None:
    assert over_budget(_run(), 1.0) is None
    assert over_budget(_run(cost_usd={"total": 3.2}), 1.0) == 3.2


def test_runs_are_matched_by_label_across_reports() -> None:
    report = [_run("fake"), _run("anthropic")]
    assert run_label(pick_run(report, None)) == run_label(_run("anthropic"))
    assert pick_run(report, run_label(_run("fake")))["config"]["provider"] == "fake"


def test_cli_exit_codes(tmp_path: Path) -> None:
    baseline, current = tmp_path / "old.json", tmp_path / "new.json"
    baseline.write_text(json.dumps([_run()]))
    current.write_text(json.dumps([_run(vitals={"value_accuracy": 0.95})]))
    assert main(["--report", str(current), "--baseline", str(baseline)]) == 0
    assert main(["--report", str(current)]) == 0  # no baseline: record only
    current.write_text(json.dumps([_run(alert_accuracy=0.9)]))
    assert main(["--report", str(current), "--baseline", str(baseline)]) == 1
    assert main(["--report", str(current), "--max-cost-usd", "0.1"]) == 1
