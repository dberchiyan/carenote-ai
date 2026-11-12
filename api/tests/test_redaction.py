import json
import re
from pathlib import Path

import pytest

from carenote.patients.synthetic import generate_patients
from carenote.pipeline.redaction import redact, reredact, unredact

PATIENTS = generate_patients()
NAMES = {n for p in PATIENTS for n in (p.given_name, p.family_name)}
CASES = [
    json.loads(line)
    for line in (Path(__file__).parents[1] / "evals/data/cases.jsonl").read_text().splitlines()
]
NUMBER = re.compile(r"\d+(?:\.\d+)?")


def test_known_patient_names_become_patient_placeholders() -> None:
    r = redact("Mrs. Anna Keller, BP 150/90. Later Mrs. Keller slept. Mr. Smith fine.", PATIENTS)
    assert r.text == "<PATIENT_1>, BP 150/90. Later <PATIENT_1> slept. <PATIENT_2> fine."
    assert r.mapping["<PATIENT_1>"] == "Mrs. Anna Keller"
    assert r.mapping["<PATIENT_2>"] == "Mr. Smith"


def test_ner_redacts_other_people_dates_and_phone_numbers() -> None:
    r = redact(
        "Daughter Julia called on 12 March 2026 from 0151 2345678. Round at 14:00.", PATIENTS
    )
    assert "Julia" not in r.text
    assert "12 March 2026" not in r.text
    assert "2345678" not in r.text
    assert "14:00" in r.text  # a time of day is not identifying
    assert unredact(r.text, r.mapping).startswith("Daughter Julia called on 12 March 2026")


@pytest.mark.parametrize(
    "text",
    [
        "<PATIENT_1>. Ondansetron 4 mg IV. Sats 94% RA. Feeling dizzy.",
        # Regression: "Sugar" was tagged as a LOCATION.
        "<PATIENT_1>. Sugar is 134, sats 96 percent on room air, pulse is 89.",
        "Blood sugar 140, weighs 72 kilos, resps 18, saturating at 95 percent.",
    ],
)
def test_clinical_words_survive_ner(text: str) -> None:
    assert redact(text, PATIENTS).text == text


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_dataset_redaction_removes_names_and_keeps_every_number(case: dict[str, str]) -> None:
    r = redact(case["text"], PATIENTS)
    for name in NAMES:
        assert not re.search(rf"\b{name}\b", r.text, re.IGNORECASE), (name, r.text)
    stripped = re.sub(r"<[A-Z]+_\d+>", "", r.text)
    assert NUMBER.findall(stripped) == NUMBER.findall(case["text"])


def test_vital_values_are_never_redacted_as_phone_numbers_or_dates() -> None:
    # Regression: Presidio tagged "168/96" as a phone number and erased a blood pressure.
    pressures = [f"{s}/{d}" for s in range(80, 230, 7) for d in range(40, 130, 9) if d < s]
    text = ". ".join(
        f"BP {bp}, pulse {60 + i % 50}, temp 37.{i % 10}" for i, bp in enumerate(pressures)
    )
    redacted = redact(text, PATIENTS).text
    assert redacted == text


@pytest.mark.parametrize(
    ("text", "kept"),
    [
        ("BP 168/96, pulse 380.", True),
        ("Blood pressure 98/60 at 14:00.", True),
        ("Seen on 03/04, call 0151 2345678.", False),
    ],
)
def test_dates_and_phones_versus_vitals(text: str, kept: bool) -> None:
    assert (redact(text, PATIENTS).text == text) is kept


def test_reredact_puts_placeholders_back_for_every_name_form() -> None:
    """A nurse may type the name without the title, or just the first or last name."""
    mapping = {"<PATIENT_1>": "Mrs. Anna Keller", "<PERSON_1>": "Dr. Weber"}
    text = "Mrs. Anna Keller was seen by Weber; Anna rested, Keller fine."
    assert reredact(text, mapping) == (
        "<PATIENT_1> was seen by <PERSON_1>; <PATIENT_1> rested, <PATIENT_1> fine."
    )
