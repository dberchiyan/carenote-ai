"""Read the offline eval reports written by `make eval` (api/evals/run.py)."""

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel


class EvalSummaryOut(BaseModel):
    cases: int
    perfect_cases: int
    errors: int
    value_accuracy: float | None
    vital_precision: float | None
    vital_recall: float | None
    symptoms_f1: float | None
    medications_f1: float | None
    patient_match_accuracy: float | None
    alert_accuracy: float | None
    implausible_kept_out: float | None
    cost_per_note_usd: float
    latency_avg_ms: float


class EvalTagOut(BaseModel):
    tag: str
    cases: int
    perfect_cases: int
    value_accuracy: float | None


class EvalCaseOut(BaseModel):
    case_id: str
    tags: list[str]
    difficulty: str
    perfect: bool
    text: str
    diffs: list[str]
    error: str | None


class EvalRunOut(BaseModel):
    report: str
    date: str
    provider: str
    model: str
    mode: str
    dataset: str
    prompt_version: str
    summary: EvalSummaryOut
    by_tag: list[EvalTagOut]
    cases: list[EvalCaseOut]


def _run(report: str, raw: dict[str, Any]) -> EvalRunOut:
    config, summary = raw["config"], raw["summary"]
    vitals = summary["vitals"]
    return EvalRunOut(
        report=report,
        date=report[:10],
        provider=config["provider"],
        model=config["model"],
        mode=config["mode"],
        dataset=Path(config["dataset"].split()[0]).stem,
        prompt_version=config["prompt_version"],
        summary=EvalSummaryOut(
            cases=summary["cases"],
            perfect_cases=summary["perfect_cases"],
            errors=summary["errors"],
            value_accuracy=vitals["value_accuracy"],
            vital_precision=vitals["precision"],
            vital_recall=vitals["recall"],
            symptoms_f1=summary["symptoms"]["f1"],
            medications_f1=summary["medications"]["f1"],
            patient_match_accuracy=summary["patient_match_accuracy"],
            alert_accuracy=summary["alert_accuracy"],
            implausible_kept_out=summary["implausible_kept_out"],
            cost_per_note_usd=summary["cost_usd"]["per_note"],
            latency_avg_ms=summary["latency_ms"]["avg"],
        ),
        by_tag=[
            EvalTagOut(
                tag=tag,
                cases=t["cases"],
                perfect_cases=t["perfect_cases"],
                value_accuracy=t["vitals"]["value_accuracy"],
            )
            for tag, t in sorted(raw["by_tag"].items())
        ],
        cases=[
            EvalCaseOut(
                case_id=c["case_id"],
                tags=c["tags"],
                difficulty=c["difficulty"],
                perfect=c.get("perfect", not c["diffs"] and c["error"] is None),
                text=c.get("text", ""),
                diffs=c["diffs"],
                error=c["error"],
            )
            for c in raw["cases"]
        ],
    )


def load_runs(directory: Path) -> list[EvalRunOut]:
    """The newest run per (provider, model, mode, dataset); newest reports first."""
    seen: set[tuple[str, str, str, str]] = set()
    runs: list[EvalRunOut] = []
    for path in sorted(directory.glob("*.json"), reverse=True):
        for raw in json.loads(path.read_text(encoding="utf-8")):
            run = _run(path.stem, raw)
            key = (run.provider, run.model, run.mode, run.dataset)
            if key not in seen:
                seen.add(key)
                runs.append(run)
    return runs
