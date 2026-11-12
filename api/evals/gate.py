"""Regression gate for eval reports: fail when a headline metric drops more than allowed.

    uv run python -m evals.gate --report evals/reports/<new>.json \\
        --baseline evals/reports/<old>.json --max-regression 0.02 --max-cost-usd 2

Compares the run with the same label (provider, model, mode, dataset) in both files. A metric
that fell by more than `max_regression` (absolute, e.g. 0.02 = 2 percentage points) fails the
gate; so does a run that cost more than the budget. Run after `make eval` so a prompt or
model change cannot silently make extraction worse.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Metric name -> how to read it from a run's `summary`. Higher is better for all of them.
HEADLINE: dict[str, Callable[[dict[str, Any]], float | None]] = {
    "vitals.value_accuracy": lambda m: m["vitals"]["value_accuracy"],
    "vitals.recall": lambda m: m["vitals"]["recall"],
    "patient_match_accuracy": lambda m: m["patient_match_accuracy"],
    "alert_accuracy": lambda m: m["alert_accuracy"],
    "symptoms.f1": lambda m: m["symptoms"]["f1"],
    "medications.f1": lambda m: m["medications"]["f1"],
}


@dataclass(frozen=True)
class Finding:
    metric: str
    baseline: float | None
    current: float | None
    delta: float | None
    failed: bool

    def __str__(self) -> str:
        def fmt(v: float | None) -> str:
            return "—" if v is None else f"{v * 100:.1f}%"

        mark = "FAIL" if self.failed else "ok"
        return f"{mark:4} {self.metric:28} {fmt(self.baseline):>7} -> {fmt(self.current):>7}"


def run_label(run: dict[str, Any]) -> str:
    c = run["config"]
    return f"{c['provider']}|{c['model']}|{c['mode']}|{c['dataset'].split()[0]}"


def pick_run(report: list[dict[str, Any]], label: str | None) -> dict[str, Any]:
    if label is None:
        return report[-1]
    for run in report:
        if run_label(run) == label:
            return run
    raise SystemExit(f"no run labelled {label!r} in the report")


def compare(
    baseline: dict[str, Any], current: dict[str, Any], max_regression: float
) -> list[Finding]:
    findings = []
    for name, read in HEADLINE.items():
        before, after = read(baseline["summary"]), read(current["summary"])
        delta = None if before is None or after is None else after - before
        failed = delta is not None and delta < -max_regression
        findings.append(Finding(name, before, after, delta, failed))
    return findings


def over_budget(current: dict[str, Any], max_cost_usd: float | None) -> float | None:
    """The run's total cost when it exceeds the budget, else None."""
    total = float(current["summary"]["cost_usd"]["total"])
    return total if max_cost_usd is not None and total > max_cost_usd else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--report", type=Path, required=True, help="the new report (.json)")
    parser.add_argument("--baseline", type=Path, help="the report to compare against (.json)")
    parser.add_argument("--max-regression", type=float, default=0.02)
    parser.add_argument("--max-cost-usd", type=float)
    args = parser.parse_args(argv)

    current_report = json.loads(args.report.read_text())
    current = pick_run(current_report, None)
    label = run_label(current)
    failed = False

    cost = over_budget(current, args.max_cost_usd)
    if cost is not None:
        print(f"FAIL budget: the run cost ${cost:.4f}, more than ${args.max_cost_usd:.2f}")
        failed = True

    if args.baseline is None or not args.baseline.exists():
        print(f"No baseline for {label}: nothing to compare, metrics recorded only.")
    else:
        baseline = pick_run(json.loads(args.baseline.read_text()), label)
        print(f"{label}  (max regression {args.max_regression * 100:.1f} p.p.)")
        for finding in compare(baseline, current, args.max_regression):
            print(finding)
            failed = failed or finding.failed
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
