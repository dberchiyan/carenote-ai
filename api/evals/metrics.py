"""Scoring one prediction against one dataset case, and aggregating scores.

Pure functions: no providers, no I/O. Tested in tests/test_eval_metrics.py.
"""

from __future__ import annotations

import math
import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from carenote.alerts.rules import RuleSet

VALUE_TOLERANCE = 0.051  # temperatures and weights are compared to one decimal


@dataclass
class Prediction:
    case_id: str
    selected_patient_id: str | None
    candidate_ids: list[str]
    vitals: dict[str, float]
    flags: dict[str, str]
    symptoms: list[str]
    medications: list[dict[str, str | None]]
    uncertain: list[str]
    transcript: str
    latency_ms: int
    llm_latency_ms: int
    cost_usd: float
    input_tokens: int
    output_tokens: int
    error: str | None = None


@dataclass
class CaseScore:
    case_id: str
    tags: list[str]
    difficulty: str
    vital_tp: int = 0  # kind found
    vital_fp: int = 0
    vital_fn: int = 0
    vital_value_ok: int = 0  # kind found with the right value
    vital_expected: int = 0
    symptom_tp: int = 0
    symptom_fp: int = 0
    symptom_fn: int = 0
    med_tp: int = 0
    med_fp: int = 0
    med_fn: int = 0
    med_detail_ok: int = 0  # name found with the right dose and route
    patient_ok: bool = False
    alert_ok: int = 0
    alert_expected: int = 0
    abnormal_expected: int = 0
    abnormal_caught: int = 0
    implausible_expected: int = 0
    implausible_kept_out: int = 0
    wer: float | None = None
    latency_ms: int = 0
    llm_latency_ms: int = 0
    cost_usd: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    error: str | None = None
    diffs: list[str] = field(default_factory=list)

    @property
    def perfect(self) -> bool:
        return not self.diffs and self.error is None


def _normalize_words(text: str) -> str:
    tokens = re.findall(r"[a-z0-9.]+", text.lower().replace("%", " percent"))
    return " ".join(t.strip(".") for t in tokens if t.strip("."))


def word_error_rate(reference: str, hypothesis: str) -> float:
    import jiwer

    return float(jiwer.wer(_normalize_words(reference), _normalize_words(hypothesis)))


def _same(a: float, b: float) -> bool:
    return math.isclose(a, b, abs_tol=VALUE_TOLERANCE)


def score_case(case: dict[str, Any], pred: Prediction, rules: RuleSet) -> CaseScore:
    s = CaseScore(case["id"], case["tags"], case["difficulty"])
    s.latency_ms, s.llm_latency_ms = pred.latency_ms, pred.llm_latency_ms
    s.cost_usd, s.input_tokens, s.output_tokens = (
        pred.cost_usd,
        pred.input_tokens,
        pred.output_tokens,
    )
    if pred.error:
        s.error = pred.error
    if "audio_reference" in case:
        s.wer = word_error_rate(case["audio_reference"], pred.transcript)

    # Vitals: kind-level precision/recall plus exact-value accuracy.
    expected = {v["kind"]: float(v["value"]) for v in case["expected_vitals"]}
    s.vital_expected = len(expected)
    for kind, value in expected.items():
        if kind in pred.vitals:
            s.vital_tp += 1
            if _same(pred.vitals[kind], value):
                s.vital_value_ok += 1
            else:
                s.diffs.append(f"{kind}: expected {value:g}, got {pred.vitals[kind]:g}")
        else:
            s.vital_fn += 1
            s.diffs.append(f"{kind}: missing (expected {value:g})")
    for kind, value in pred.vitals.items():
        if kind not in expected:
            s.vital_fp += 1
            s.diffs.append(f"{kind}: unexpected value {value:g}")

    # Alerts: the flag the system would show for each expected vital.
    for kind, value in expected.items():
        want = rules.flag(kind, value)
        got = pred.flags.get(kind)
        s.alert_expected += 1
        s.alert_ok += got == want
        if want != "normal":
            s.abnormal_expected += 1
            s.abnormal_caught += got == want

    # Implausible values must stay out of the vitals.
    for kind in case["expected_uncertain_kinds"]:
        s.implausible_expected += 1
        s.implausible_kept_out += kind not in pred.vitals

    want_symptoms, got_symptoms = set(case["expected_symptoms"]), set(pred.symptoms)
    s.symptom_tp = len(want_symptoms & got_symptoms)
    s.symptom_fp = len(got_symptoms - want_symptoms)
    s.symptom_fn = len(want_symptoms - got_symptoms)
    if want_symptoms != got_symptoms:
        s.diffs.append(f"symptoms: expected {sorted(want_symptoms)}, got {sorted(got_symptoms)}")

    want_meds = {m["name"]: m for m in case["expected_medications"]}
    got_meds = {str(m["name"]): m for m in pred.medications}
    s.med_tp = len(want_meds.keys() & got_meds.keys())
    s.med_fp = len(got_meds.keys() - want_meds.keys())
    s.med_fn = len(want_meds.keys() - got_meds.keys())
    for name in want_meds.keys() & got_meds.keys():
        w, g = want_meds[name], got_meds[name]
        if (w["dose"], w["route"]) == (g["dose"], g["route"]):
            s.med_detail_ok += 1
        else:
            s.diffs.append(
                f"{name}: expected {w['dose']} {w['route']}, got {g['dose']} {g['route']}"
            )
    if want_meds.keys() != got_meds.keys():
        s.diffs.append(f"medications: expected {sorted(want_meds)}, got {sorted(got_meds)}")

    candidates_ok = set(case["expected_patient_candidates"]) <= set(pred.candidate_ids)
    s.patient_ok = pred.selected_patient_id == case["expected_patient_id"] and candidates_ok
    if not s.patient_ok:
        s.diffs.append(
            f"patient: expected {case['expected_patient_id'] or 'nurse must pick'}, "
            f"got {pred.selected_patient_id or 'nurse must pick'}"
        )
    return s


def _ratio(num: float, den: float) -> float | None:
    return round(num / den, 4) if den else None


def _f1(p: float | None, r: float | None) -> float | None:
    if p is None or r is None or p + r == 0:
        return None
    return round(2 * p * r / (p + r), 4)


def _pct(values: list[int], q: float) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, round(q * (len(ordered) - 1)))]


def aggregate(scores: list[CaseScore]) -> dict[str, Any]:
    def total(attr: str) -> int:
        return int(sum(getattr(s, attr) for s in scores))

    vp = _ratio(total("vital_tp"), total("vital_tp") + total("vital_fp"))
    vr = _ratio(total("vital_tp"), total("vital_tp") + total("vital_fn"))
    sp = _ratio(total("symptom_tp"), total("symptom_tp") + total("symptom_fp"))
    sr = _ratio(total("symptom_tp"), total("symptom_tp") + total("symptom_fn"))
    mp = _ratio(total("med_tp"), total("med_tp") + total("med_fp"))
    mr = _ratio(total("med_tp"), total("med_tp") + total("med_fn"))
    wers = [s.wer for s in scores if s.wer is not None]
    latencies = [s.latency_ms for s in scores]
    cost = sum(s.cost_usd for s in scores)
    return {
        "cases": len(scores),
        "errors": sum(1 for s in scores if s.error),
        "perfect_cases": sum(1 for s in scores if s.perfect),
        "vitals": {
            "precision": vp,
            "recall": vr,
            "f1": _f1(vp, vr),
            "value_accuracy": _ratio(total("vital_value_ok"), total("vital_expected")),
        },
        "symptoms": {"precision": sp, "recall": sr, "f1": _f1(sp, sr)},
        "medications": {
            "precision": mp,
            "recall": mr,
            "f1": _f1(mp, mr),
            "dose_route_accuracy": _ratio(total("med_detail_ok"), total("med_tp")),
        },
        "patient_match_accuracy": _ratio(sum(s.patient_ok for s in scores), len(scores)),
        "alert_accuracy": _ratio(total("alert_ok"), total("alert_expected")),
        "abnormal_recall": _ratio(total("abnormal_caught"), total("abnormal_expected")),
        "implausible_kept_out": _ratio(
            total("implausible_kept_out"), total("implausible_expected")
        ),
        "wer": round(sum(wers) / len(wers), 4) if wers else None,
        "latency_ms": {
            "avg": round(sum(latencies) / len(latencies)) if latencies else 0,
            "p95": _pct(latencies, 0.95),
            "llm_avg": round(sum(s.llm_latency_ms for s in scores) / len(scores)) if scores else 0,
        },
        "tokens": {"input": total("input_tokens"), "output": total("output_tokens")},
        "cost_usd": {
            "total": round(cost, 4),
            "per_note": round(cost / len(scores), 6) if scores else 0,
        },
    }


def breakdown(scores: list[CaseScore], key: str) -> dict[str, dict[str, Any]]:
    groups: dict[str, list[CaseScore]] = defaultdict(list)
    for s in scores:
        for value in s.tags if key == "tag" else [s.difficulty]:
            groups[value].append(s)
    return {name: aggregate(group) for name, group in sorted(groups.items())}
