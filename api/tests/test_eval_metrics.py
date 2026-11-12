import json
from pathlib import Path
from typing import Any

from evals import run as eval_run
from evals.metrics import Prediction, aggregate, breakdown, score_case, word_error_rate

from carenote.alerts.rules import default_rules

CASE: dict[str, Any] = {
    "id": "case-x",
    "tags": ["plain"],
    "difficulty": "easy",
    "expected_patient_id": "p1",
    "expected_patient_candidates": ["p1"],
    "expected_vitals": [
        {"kind": "systolic_bp", "value": 150.0, "unit": "mm[Hg]"},
        {"kind": "diastolic_bp", "value": 90.0, "unit": "mm[Hg]"},
        {"kind": "temperature", "value": 37.8, "unit": "Cel"},
    ],
    "expected_symptoms": ["headache"],
    "expected_medications": [{"name": "paracetamol", "dose": "500 mg", "route": "oral"}],
    "expected_uncertain_kinds": ["heart_rate"],
}


def prediction(**overrides: Any) -> Prediction:
    base: dict[str, Any] = {
        "case_id": "case-x",
        "selected_patient_id": "p1",
        "candidate_ids": ["p1"],
        "vitals": {"systolic_bp": 150.0, "diastolic_bp": 90.0, "temperature": 37.8},
        "flags": {"systolic_bp": "warning", "diastolic_bp": "normal", "temperature": "normal"},
        "symptoms": ["headache"],
        "medications": [{"name": "paracetamol", "dose": "500 mg", "route": "oral"}],
        "uncertain": [],
        "transcript": "",
        "latency_ms": 10,
        "llm_latency_ms": 5,
        "cost_usd": 0.01,
        "input_tokens": 100,
        "output_tokens": 50,
    }
    return Prediction(**(base | overrides))


def test_a_perfect_prediction_scores_perfectly() -> None:
    score = score_case(CASE, prediction(), default_rules())
    assert score.perfect
    summary = aggregate([score])
    assert summary["vitals"] == {"precision": 1.0, "recall": 1.0, "f1": 1.0, "value_accuracy": 1.0}
    assert summary["patient_match_accuracy"] == 1.0
    assert summary["alert_accuracy"] == 1.0
    assert summary["abnormal_recall"] == 1.0
    assert summary["implausible_kept_out"] == 1.0


def test_wrong_values_missing_and_extra_vitals() -> None:
    pred = prediction(
        vitals={"systolic_bp": 145.0, "diastolic_bp": 90.0, "heart_rate": 380.0},
        flags={"systolic_bp": "warning", "diastolic_bp": "normal"},
    )
    score = score_case(CASE, pred, default_rules())
    assert (score.vital_tp, score.vital_fp, score.vital_fn, score.vital_value_ok) == (2, 1, 1, 1)
    assert score.implausible_kept_out == 0  # the implausible pulse leaked into the vitals
    assert any("systolic_bp: expected 150, got 145" in d for d in score.diffs)
    summary = aggregate([score])
    assert summary["vitals"]["value_accuracy"] == round(1 / 3, 4)
    assert summary["alert_accuracy"] == round(2 / 3, 4)


def test_patient_match_requires_candidates_and_respects_ambiguity() -> None:
    ambiguous = CASE | {"expected_patient_id": None, "expected_patient_candidates": ["p1", "p2"]}
    assert score_case(
        ambiguous, prediction(selected_patient_id=None, candidate_ids=["p1", "p2"]), default_rules()
    ).patient_ok
    assert not score_case(ambiguous, prediction(), default_rules()).patient_ok
    assert not score_case(
        ambiguous, prediction(selected_patient_id=None), default_rules()
    ).patient_ok


def test_medication_details_and_breakdown() -> None:
    pred = prediction(medications=[{"name": "paracetamol", "dose": "1 g", "route": "oral"}])
    score = score_case(CASE, pred, default_rules())
    assert (score.med_tp, score.med_detail_ok) == (1, 0)
    by_tag = breakdown([score], "tag")
    assert by_tag["plain"]["medications"]["dose_route_accuracy"] == 0.0


def test_wer_ignores_case_and_punctuation() -> None:
    assert word_error_rate("BP 150/90, pulse 88.", "bp 150/90 pulse 88") == 0.0
    assert word_error_rate("pulse 88", "pulse 89") == 0.5


def test_runner_writes_markdown_and_json(tmp_path: Path) -> None:
    eval_run.main(["--limit", "5", "--out", str(tmp_path)])
    [md] = list(tmp_path.glob("*.md"))
    assert "| Vitals — value accuracy |" in md.read_text()
    data = json.loads(md.with_suffix(".json").read_text())
    assert data[0]["summary"]["cases"] == 5
    assert data[0]["config"]["model"] == "rule-based-v1"


def test_compare_writes_one_side_by_side_report(tmp_path: Path) -> None:
    eval_run.main(["--limit", "3", "--compare", "fake", "fake", "--out", str(tmp_path)])
    [md] = list(tmp_path.glob("*-vs-*.md"))
    header = next(line for line in md.read_text().splitlines() if line.startswith("| Metric"))
    assert header.count("fake-rule-based-v1-text") == 2


def test_paraphrases_that_change_facts_are_rejected() -> None:
    from evals.paraphrase import paraphrase_cases

    case = {"id": "c", "text": "Mrs. Anna Keller, pulse 88. Denies chest pain.", "tags": ["plain"]}
    good = paraphrase_cases(
        [case], lambda _: "Anna Keller — Mrs. — pulse is 88, denies chest pain."
    )
    assert good[0]["tags"][-1] == "paraphrased"
    for bad in (
        "Mrs. Anna Keller, pulse 86. Denies chest pain.",  # changed a number
        "Mrs. Keller, pulse 88. Denies chest pain.",  # dropped a name
        "Mrs. Anna Keller, pulse 88, chest pain.",  # lost the negation
    ):
        [row] = paraphrase_cases([case], lambda _, bad=bad: bad)
        assert row["text"] == case["text"]
        assert row["tags"][-1] == "paraphrase_rejected"
