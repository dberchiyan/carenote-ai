"""Run the real pipeline on the synthetic dataset and write a report.

    uv run python -m evals.run                         # rule-based baseline, text mode
    uv run python -m evals.run --provider anthropic    # Claude (CARENOTE_ANTHROPIC_API_KEY)
    uv run python -m evals.run --mode audio --transcriber openai --provider anthropic
    uv run python -m evals.run --compare fake anthropic   # side-by-side report

Reports go to evals/reports/<date>-<label>.md and .json.
"""

from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import hashlib
import json
import subprocess
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

from carenote.alerts.rules import default_rules
from carenote.config import Settings, get_settings
from carenote.contracts.llm import LLMProvider, ProviderError, TranscriptionProvider
from carenote.patients.synthetic import generate_patients
from carenote.pipeline import redaction
from carenote.pipeline.core import PipelineError, run_text_pipeline
from carenote.pipeline.prompts import EXTRACT_PROMPT_VERSION, load_prompt
from carenote.providers.factory import build_llm, build_transcription
from carenote.providers.fake import FakeTranscription
from evals.metrics import CaseScore, Prediction, aggregate, breakdown, score_case

DATA = Path(__file__).parent / "data"
REPORTS = Path(__file__).parent / "reports"
ProviderName = Literal["fake", "anthropic", "openai"]
Mode = Literal["text", "audio"]


@dataclass
class RunConfig:
    provider: ProviderName
    mode: Mode
    transcriber: Literal["fake", "openai"]
    model: str
    prompt_version: str
    cases: int
    dataset: str
    # Provenance: enough to tell two runs apart even when nothing above changed.
    prompt_sha256: str = ""
    rules_version: int = 0
    sdk: dict[str, str] = field(default_factory=dict)
    git_commit: str | None = None
    ran_at: str = ""


def provenance() -> dict[str, Any]:
    """Prompt hash, rules version, SDK versions and the commit, for the report header."""
    from importlib.metadata import PackageNotFoundError, version

    sdk = {}
    for package in ("anthropic", "openai", "faster-whisper", "presidio-analyzer", "spacy"):
        with contextlib.suppress(PackageNotFoundError):
            sdk[package] = version(package)
    try:
        commit: str | None = (
            subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],  # noqa: S607
                capture_output=True, text=True, check=True, timeout=5,
            ).stdout.strip()
            or None
        )  # fmt: skip
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        commit = None
    return {
        "prompt_sha256": hashlib.sha256(load_prompt().system.encode()).hexdigest()[:12],
        "rules_version": default_rules().version,
        "sdk": sdk,
        "git_commit": commit,
        "ran_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
    }


def load_cases(limit: int | None = None, dataset: str = "cases") -> list[dict[str, Any]]:
    rows = [json.loads(line) for line in (DATA / f"{dataset}.jsonl").read_text().splitlines()]
    return rows[:limit] if limit else rows


def _llm(provider: ProviderName) -> LLMProvider:
    settings = get_settings()
    return build_llm(Settings(**{**settings.model_dump(), "llm_provider": provider}))


def _transcriber(name: str, cases: list[dict[str, Any]]) -> TranscriptionProvider:
    if name == "fake":
        # Maps each dataset file to its source text: exercises the audio path, WER is 0 by design.
        known = {}
        for case in cases:
            path = DATA / case["audio_file"]
            if path.exists():
                known[FakeTranscription.digest(path.read_bytes())] = case["text"]
        return FakeTranscription(known)
    settings = get_settings()
    return build_transcription(
        Settings(**{**settings.model_dump(), "transcription_provider": name})
    )


def predict(
    case: dict[str, Any],
    llm: LLMProvider,
    transcriber: TranscriptionProvider | None,
) -> Prediction:
    patients = generate_patients()
    ward = [p for p in patients if p.ward == case["ward"]]
    started = time.perf_counter()
    transcript = case["text"]
    transcription_cost = 0.0
    try:
        if transcriber is not None:
            path = DATA / case["audio_file"]
            result = transcriber.transcribe(path.read_bytes(), path.name, "audio/wav", None)
            transcript, transcription_cost = result.text, result.cost_usd
        out = run_text_pipeline(transcript, ward_patients=ward, known_patients=patients, llm=llm)
    except (PipelineError, ProviderError, OSError) as exc:
        return Prediction(
            case["id"], None, [], {}, {}, [], [], [], transcript,
            round((time.perf_counter() - started) * 1000), 0, transcription_cost, 0, 0, str(exc),
        )  # fmt: skip
    return Prediction(
        case_id=case["id"],
        selected_patient_id=str(out.match.selected_id) if out.match.selected_id else None,
        candidate_ids=[str(c.patient_id) for c in out.match.candidates],
        vitals={v.kind: v.value for v in out.extraction.vitals},
        flags=dict(out.flags),
        symptoms=out.extraction.symptoms,
        medications=[
            {"name": m.name, "dose": m.dose, "route": m.route} for m in out.extraction.medications
        ],
        uncertain=out.extraction.uncertain,
        transcript=transcript,
        latency_ms=round((time.perf_counter() - started) * 1000),
        llm_latency_ms=out.usage.latency_ms,
        cost_usd=out.usage.cost_usd + transcription_cost,
        input_tokens=out.usage.input_tokens,
        output_tokens=out.usage.output_tokens,
    )


def run(
    provider: ProviderName,
    mode: Mode,
    transcriber_name: Literal["fake", "openai"],
    cases: list[dict[str, Any]],
    progress: Callable[[str], None] = print,
    dataset: str = "cases",
) -> tuple[RunConfig, list[CaseScore], list[Prediction]]:
    llm = _llm(provider)
    redaction.warm_up()  # load the NLP model before timing anything
    transcriber = _transcriber(transcriber_name, cases) if mode == "audio" else None
    rules = default_rules()
    scores, predictions = [], []
    model = "?"
    for i, case in enumerate(cases, start=1):
        if mode == "audio":
            case = {**case, "audio_reference": case["text"]}
        pred = predict(case, llm, transcriber)
        scores.append(score_case(case, pred, rules))
        predictions.append(pred)
        if pred.error is None and model == "?":
            model = getattr(llm, "model", None) or "rule-based-v1"
        progress(f"  [{i:3}/{len(cases)}] {case['id']} {'ok' if scores[-1].perfect else 'diff'}")
    config = RunConfig(
        provider=provider,
        mode=mode,
        transcriber=transcriber_name if mode == "audio" else "fake",
        model=model,
        prompt_version=EXTRACT_PROMPT_VERSION,
        cases=len(cases),
        dataset=f"evals/data/{dataset}.jsonl" + (" (seed 42)" if dataset == "cases" else ""),
        **provenance(),
    )
    return config, scores, predictions


# --- Reports --------------------------------------------------------------------------------


def _fmt(value: Any, pct: bool = True) -> str:
    if value is None:
        return "—"
    if pct and isinstance(value, float):
        return f"{value * 100:.1f}%"
    return str(value)


HEADLINE: tuple[tuple[str, Callable[[dict[str, Any]], Any], bool], ...] = (
    ("Vitals — value accuracy", lambda m: m["vitals"]["value_accuracy"], True),
    ("Vitals — precision", lambda m: m["vitals"]["precision"], True),
    ("Vitals — recall", lambda m: m["vitals"]["recall"], True),
    ("Symptoms — F1", lambda m: m["symptoms"]["f1"], True),
    ("Medications — F1", lambda m: m["medications"]["f1"], True),
    (
        "Medications — dose & route accuracy",
        lambda m: m["medications"]["dose_route_accuracy"],
        True,
    ),
    ("Patient match accuracy", lambda m: m["patient_match_accuracy"], True),
    ("Alert accuracy", lambda m: m["alert_accuracy"], True),
    ("Abnormal values flagged", lambda m: m["abnormal_recall"], True),
    ("Implausible values kept out of vitals", lambda m: m["implausible_kept_out"], True),
    ("Word error rate (audio)", lambda m: m["wer"], True),
    ("Perfect cases", lambda m: f"{m['perfect_cases']}/{m['cases']}", False),
    ("Errors", lambda m: m["errors"], False),
    (
        "Latency avg / p95 (ms)",
        lambda m: f"{m['latency_ms']['avg']} / {m['latency_ms']['p95']}",
        False,
    ),
    ("Tokens in / out", lambda m: f"{m['tokens']['input']:,} / {m['tokens']['output']:,}", False),
    ("Cost per note", lambda m: f"${m['cost_usd']['per_note']:.5f}", False),
    ("Total cost", lambda m: f"${m['cost_usd']['total']:.4f}", False),
)


def _label(config: RunConfig) -> str:
    stem = Path(config.dataset.split()[0]).stem
    suffix = "" if stem == "cases" else f"-{stem.removeprefix('cases_')}"
    return f"{config.provider}-{config.model}-{config.mode}{suffix}".replace("/", "_")


def markdown_report(runs: list[tuple[RunConfig, list[CaseScore]]], date: str) -> str:
    names = [_label(c) for c, _ in runs]
    first = runs[0][0]
    summaries = [aggregate(s) for _, s in runs]
    lines = [
        f"# CareNote AI — evaluation report ({date})",
        "",
        "Synthetic data only. "
        + ", ".join(
            f"`{c.provider}` · model `{c.model}` · {c.mode} mode"
            + (f" · transcriber `{c.transcriber}`" if c.mode == "audio" else "")
            for c, _ in runs
        )
        + f" · prompt `{first.prompt_version}` · {first.cases} cases from {first.dataset}.",
        "",
        f"Provenance: prompt sha256 `{first.prompt_sha256}` · rules v{first.rules_version} · "
        + " · ".join(f"{k} {v}" for k, v in first.sdk.items())
        + (f" · commit `{first.git_commit}`" if first.git_commit else "")
        + f" · ran {first.ran_at}.",
        "",
        "## Summary",
        "",
        "| Metric | " + " | ".join(names) + " |",
        "|---|" + "---|" * len(names),
    ]
    for title, get, pct in HEADLINE:
        lines.append(f"| {title} | " + " | ".join(_fmt(get(m), pct) for m in summaries) + " |")

    for key, heading in (("tag", "By tag"), ("difficulty", "By difficulty")):
        lines += ["", f"## {heading}", ""]
        groups = [breakdown(s, key) for _, s in runs]
        header = "| " + heading.split()[-1].capitalize() + " | n | "
        header += " | ".join(f"value acc. · {n}" for n in names) + " | "
        header += " | ".join(f"patient · {n}" for n in names) + " |"
        lines += [header, "|---|---|" + "---|" * (2 * len(names))]
        for group in groups[0]:
            row = [group, str(groups[0][group]["cases"])]
            row += [_fmt(g.get(group, {}).get("vitals", {}).get("value_accuracy")) for g in groups]
            row += [_fmt(g.get(group, {}).get("patient_match_accuracy")) for g in groups]
            lines.append("| " + " | ".join(row) + " |")

    for (_, scores), name in zip(runs, names, strict=True):
        misses = [s for s in scores if not s.perfect][:15]
        lines += [
            "",
            f"## Imperfect cases — {name} ({sum(not s.perfect for s in scores)} total, first 15)",
            "",
        ]
        if not misses:
            lines.append("None.")
        for s in misses:
            detail = "; ".join(s.diffs[:4]) if s.diffs else s.error
            lines.append(f"- `{s.case_id}` ({', '.join(s.tags)}): {detail}")

    lines += [
        "",
        "## How to read this",
        "",
        "- **Value accuracy**: expected vital values extracted with the exact value "
        "(±0.05) / all expected values. **Precision/recall** are on the vital kind.",
        "- **Patient match**: the auto-selected patient equals the expected one (or nobody, when "
        "the note is ambiguous) *and* every plausible patient is offered as a candidate.",
        "- **Alert accuracy**: the flag shown for each expected vital equals the flag its true "
        "value deserves under `alerts/rules.yaml`.",
        "- The rule-based `fake` provider was written alongside the dataset templates; its score "
        "is a baseline for the harness, not evidence of real-world accuracy.",
        "- Generated by `make eval` (`api/evals/run.py`).",
    ]
    return "\n".join(lines) + "\n"


def write_reports(
    runs: list[tuple[RunConfig, list[CaseScore], list[Prediction]]], out: Path, date: str
) -> Path:
    out.mkdir(parents=True, exist_ok=True)
    label = "-vs-".join(_label(c) for c, _, _ in runs)
    md = out / f"{date}-{label}.md"
    md.write_text(markdown_report([(c, s) for c, s, _ in runs], date), encoding="utf-8")
    payload = [
        {
            "config": asdict(c),
            "summary": aggregate(s),
            "by_tag": breakdown(s, "tag"),
            "by_difficulty": breakdown(s, "difficulty"),
            "cases": [
                {**asdict(x), "perfect": x.perfect, "text": p.transcript}
                for x, p in zip(s, preds, strict=True)
            ],
        }
        for c, s, preds in runs
    ]
    md.with_suffix(".json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return md


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--provider", choices=("fake", "anthropic", "openai"), default="fake")
    parser.add_argument(
        "--compare", nargs=2, choices=("fake", "anthropic", "openai"), metavar="PROVIDER"
    )
    parser.add_argument("--mode", choices=("text", "audio"), default="text")
    parser.add_argument("--transcriber", choices=("fake", "openai"), default="fake")
    parser.add_argument("--limit", type=int, help="only the first N cases")
    parser.add_argument(
        "--dataset",
        choices=("cases", "cases_paraphrased", "cases_holdout", "cases_corrections"),
        default="cases",
        help="template cases, LLM paraphrases (`evals.paraphrase`), hand-written held-out "
        "cases, or cases exported from nurse corrections (AI quality page)",
    )
    parser.add_argument("--out", type=Path, default=REPORTS)
    parser.add_argument(
        "--max-cost-usd",
        type=float,
        help="abort before running when the estimated cost exceeds this (cases x $0.02)",
    )
    args = parser.parse_args(argv)

    cases = load_cases(args.limit, args.dataset)
    if args.mode == "audio" and not (DATA / cases[0]["audio_file"]).exists():
        parser.error("audio files missing: run `make dataset-audio` first")
    providers = args.compare or [args.provider]
    paid = [p for p in providers if p != "fake"]
    estimate = len(cases) * len(paid) * 0.02  # generous per-note ceiling at list prices
    if args.max_cost_usd is not None and estimate > args.max_cost_usd:
        parser.error(
            f"estimated cost ${estimate:.2f} exceeds the budget ${args.max_cost_usd:.2f}; "
            "use --limit"
        )
    runs = []
    for provider in providers:
        print(f"Running {provider} ({args.mode} mode) on {len(cases)} cases…")
        runs.append(run(provider, args.mode, args.transcriber, cases, dataset=args.dataset))
    path = write_reports(runs, args.out, dt.date.today().isoformat())
    summary = aggregate(runs[-1][1])
    print(
        f"\nValue accuracy {_fmt(summary['vitals']['value_accuracy'])} · patient match "
        f"{_fmt(summary['patient_match_accuracy'])} · "
        f"cost/note ${summary['cost_usd']['per_note']:.5f}"
    )
    print(f"Report: {path}")


if __name__ == "__main__":
    main()
