import json
import re
from collections import Counter
from pathlib import Path

import pytest
from evals.generate import SPOKEN_SYMPTOMS, TAG_PLAN, generate_cases, write_dataset
from evals.numbers import number_to_words

from carenote.clinical.vitals import VITALS
from carenote.clinical.vocabulary import MEDICATIONS, SYMPTOMS
from carenote.patients.synthetic import generate_patients

CASES = generate_cases()


def test_output_is_byte_identical_for_a_fixed_seed(tmp_path: Path) -> None:
    a = write_dataset(generate_cases(seed=42), 42, tmp_path / "a").read_bytes()
    b = write_dataset(generate_cases(seed=42), 42, tmp_path / "b").read_bytes()
    assert a == b


def test_different_seed_gives_different_cases() -> None:
    assert [c.text for c in generate_cases(seed=1)] != [c.text for c in generate_cases(seed=2)]


def test_120_cases_with_planned_tags() -> None:
    assert len(CASES) == 120
    assert len({c.id for c in CASES}) == 120
    tags = Counter(t for c in CASES for t in c.tags)
    for tag, count in TAG_PLAN:
        if tag != "mixed":
            assert tags[tag] >= count
    assert tags["background_noise"] == 36


def test_every_case_is_written_as_jsonl(tmp_path: Path) -> None:
    path = write_dataset(CASES, 42, tmp_path)
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    assert len(rows) == 120
    assert set(rows[0]) >= {
        "id",
        "text",
        "expected_patient_id",
        "expected_vitals",
        "expected_symptoms",
        "expected_medications",
        "difficulty",
        "tags",
    }
    assert len(json.loads((tmp_path / "patients.json").read_text())) == 30


def test_expected_patients_exist_and_share_the_note_ward() -> None:
    patients = {str(p.id): p for p in generate_patients()}
    for case in CASES:
        for candidate in case.expected_patient_candidates:
            assert patients[candidate].ward == case.ward
        if "two_patients" in case.tags or "ambiguous_name" in case.tags:
            assert case.expected_patient_id is None
            assert len(case.expected_patient_candidates) >= 2
        else:
            assert case.expected_patient_id in patients


@pytest.mark.parametrize("case", [c for c in CASES if "numbers_as_words" not in c.tags], ids=str)
def test_expected_values_are_spoken_in_the_text(case: object) -> None:
    from evals.generate import Case, fmt

    assert isinstance(case, Case)
    numbers = set(re.findall(r"\d+(?:\.\d+)?", case.text))
    for vital in case.expected_vitals:
        decimals = 1 if vital.kind in ("temperature", "weight") else 0
        assert fmt(vital.value, decimals) in numbers, (vital, case.text)


def test_expected_values_are_plausible_and_bp_is_physiological() -> None:
    for case in CASES:
        values = {v.kind: v.value for v in case.expected_vitals}
        for kind, value in values.items():
            lo, hi = VITALS[kind].plausible
            assert lo <= value <= hi, (case.id, kind, value)
        if "systolic_bp" in values and "diastolic_bp" in values:
            assert values["diastolic_bp"] < values["systolic_bp"]


def test_implausible_cases_list_the_bad_kind_as_uncertain() -> None:
    for case in CASES:
        if "implausible_value" in case.tags:
            assert case.expected_uncertain_kinds
            assert not {v.kind for v in case.expected_vitals} & set(case.expected_uncertain_kinds)


def test_vocabularies_are_consistent() -> None:
    assert set(SPOKEN_SYMPTOMS) == set(SYMPTOMS)
    for case in CASES:
        assert set(case.expected_symptoms) <= set(SYMPTOMS)
        for med in case.expected_medications:
            assert (med.dose, med.route) in MEDICATIONS[med.name]


@pytest.mark.parametrize(
    ("text", "colloquial", "words"),
    [
        ("88", False, "eighty-eight"),
        ("150", False, "one hundred fifty"),
        ("150", True, "one fifty"),
        ("105", True, "one hundred and five"),
        ("37.8", False, "thirty-seven point eight"),
        ("40", False, "forty"),
    ],
)
def test_number_to_words(text: str, colloquial: bool, words: str) -> None:
    assert number_to_words(text, colloquial) == words
