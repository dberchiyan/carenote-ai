import pytest

from carenote.alerts.rules import RuleSet, default_rules, load_rules
from carenote.clinical.speech import words_to_number
from carenote.contracts.extraction import Extraction, Medication, Vital
from carenote.pipeline.validate import validate_extraction
from carenote.providers.fake import rule_based_extract


@pytest.mark.parametrize(
    ("words", "number"),
    [
        ("one hundred fifty", "150"),
        ("one fifty", "150"),
        ("one hundred and five", "105"),
        ("thirty-seven point eight", "37.8"),
        ("ninety-eight", "98"),
        ("one twenty-one", "121"),
    ],
)
def test_words_to_number(words: str, number: str) -> None:
    assert words_to_number(words) == number


def _vitals(text: str) -> dict[str, float]:
    return {v.kind: v.value for v in rule_based_extract(text).vitals}


def test_plain_and_abbreviated_vitals() -> None:
    assert _vitals("BP 150/90, HR 88, RR 18, T 37.8, sats 94% on RA, BG 140") == {
        "systolic_bp": 150, "diastolic_bp": 90, "heart_rate": 88, "respiratory_rate": 18,
        "temperature": 37.8, "spo2": 94, "blood_glucose": 140,
    }  # fmt: skip


def test_value_spoken_before_its_label() -> None:
    """Nurses also say "38 temperature, 88 pulse" and "94 percent sats"."""
    assert _vitals("John, 38 temperature, 88 pulse") == {"temperature": 38, "heart_rate": 88}
    assert _vitals("94 percent sats, 18 resps, 37.5 degrees temp") == {
        "spo2": 94, "respiratory_rate": 18, "temperature": 37.5,
    }  # fmt: skip
    # A value already claimed by a label on its left is not read twice.
    assert _vitals("pulse 88 temperature 38") == {"heart_rate": 88, "temperature": 38}


def test_punctuation_between_value_and_label_is_ignored() -> None:
    """Speech-to-text often writes dictation as a list: "80, pulse" or "pulse, 80"."""
    assert _vitals("Smith, 80, pulse, headache.") == {"heart_rate": 80}
    assert _vitals("pulse, 80, temperature: 37.9, sats, 94.") == {
        "heart_rate": 80, "temperature": 37.9, "spo2": 94,
    }  # fmt: skip


def test_self_correction_keeps_the_corrected_value() -> None:
    assert _vitals("Blood pressure 140... no, sorry, 145 over 90")["systolic_bp"] == 145
    assert _vitals("sats 86 percent on room air, correction, 90")["spo2"] == 90


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # The "Self-correction" example on the record screen.
        (
            "Mr. John Smith, pulse 72, BP 140 over 85, sorry, correction, 145 over 85, temp 36.8.",
            {"heart_rate": 72, "systolic_bp": 145, "diastolic_bp": 85, "temperature": 36.8},
        ),
        ("BP 140 over 85, sorry, 145 over 85", {"systolic_bp": 145, "diastolic_bp": 85}),
        ("BP 140/85, correction 145/85", {"systolic_bp": 145, "diastolic_bp": 85}),
        ("BP 140 over 85, no wait, 150 over 90", {"systolic_bp": 150, "diastolic_bp": 90}),
        (
            "blood pressure 140 over 85, I mean BP 150 over 95",
            {"systolic_bp": 150, "diastolic_bp": 95},
        ),
        ("pulse 72, no wait, pulse 76", {"heart_rate": 76}),
        ("temp 37.2, I mean 37.4", {"temperature": 37.4}),
        ("sats 91 percent, sorry, 93", {"spo2": 93}),
        ("pulse seventy two, scratch that, seventy six", {"heart_rate": 76}),
    ],
)
def test_self_correction_variants(text: str, expected: dict[str, float]) -> None:
    vitals = rule_based_extract(text).vitals
    assert {v.kind: v.value for v in vitals} == expected
    assert len(vitals) == len(expected), "the retracted value must not survive as a duplicate"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "BP 120 over 80, no chest pain, pulse 70",
            {"systolic_bp": 120, "diastolic_bp": 80, "heart_rate": 70},
        ),
        ("pulse 72, sorry to report she fell, temp 37.1", {"heart_rate": 72, "temperature": 37.1}),
    ],
)
def test_words_like_no_or_sorry_are_not_corrections_on_their_own(
    text: str, expected: dict[str, float]
) -> None:
    assert {v.kind: v.value for v in rule_based_extract(text).vitals} == expected


def test_source_text_points_at_the_original_words() -> None:
    vital = rule_based_extract("Temperature thirty-seven point eight degrees.").vitals[0]
    assert vital.value == 37.8
    assert vital.source_text == "Temperature thirty-seven point eight degrees"


def test_negated_symptoms_are_not_extracted() -> None:
    result = rule_based_extract("Complains of a headache. Denies chest pain. No nausea.")
    assert result.symptoms == ["headache"]


def test_medication_dose_and_route() -> None:
    meds = rule_based_extract("Gave one gram paracetamol IV. Pulse 80.").medications
    assert [(m.name, m.dose, m.route) for m in meds] == [("paracetamol", "1 gram", "iv")]


def test_validation_moves_implausible_values_to_uncertain() -> None:
    raw = Extraction(
        patient_mention=None,
        vitals=[
            Vital(kind="heart_rate", value=380, unit="/min", source_text="pulse 380"),
            Vital(kind="spo2", value=97, unit="%", source_text="sats 97"),
        ],
        symptoms=[],
        medications=[],
        free_text_summary="",
        uncertain=[],
    )
    result = validate_extraction(raw)
    assert [v.kind for v in result.vitals] == ["spo2"]
    assert any("pulse 380" in u for u in result.uncertain)


def test_validation_normalizes_units_and_doses() -> None:
    raw = Extraction(
        patient_mention=None,
        vitals=[
            Vital(kind="temperature", value=100.4, unit="F", source_text="100.4 F"),
            Vital(kind="weight", value=154, unit="lbs", source_text="154 lbs"),
            Vital(kind="blood_glucose", value=7.0, unit="mmol/L", source_text="7 mmol"),
        ],
        symptoms=["Headache", "headache"],
        medications=[Medication(name="Paracetamol", dose="1 gram", route="PO", source_text="x")],
        free_text_summary="",
        uncertain=[],
    )
    result = validate_extraction(raw)
    assert {(v.kind, v.value, v.unit) for v in result.vitals} == {
        ("temperature", 38.0, "Cel"), ("weight", 69.9, "kg"), ("blood_glucose", 126, "mg/dL"),
    }  # fmt: skip
    assert result.symptoms == ["headache"]
    med = result.medications[0]
    assert (med.name, med.dose, med.route) == ("paracetamol", "1 g", "oral")


def test_duplicate_values_keep_the_last_and_say_so() -> None:
    raw = rule_based_extract("Pulse 80. Later pulse 96.")
    result = validate_extraction(raw)
    assert [v.value for v in result.vitals] == [96]
    assert any("Several values" in u for u in result.uncertain)


@pytest.mark.parametrize(
    ("kind", "value", "flag"),
    [
        ("systolic_bp", 120, "normal"), ("systolic_bp", 150, "warning"),
        ("systolic_bp", 185, "critical"), ("systolic_bp", 85, "critical"),
        ("spo2", 92, "warning"), ("spo2", 88, "critical"), ("spo2", 99, "normal"),
        ("temperature", 38.5, "warning"), ("weight", 300, "normal"),
    ],
)  # fmt: skip
def test_alert_rules(kind: str, value: float, flag: str) -> None:
    assert default_rules().flag(kind, value) == flag  # type: ignore[arg-type]


def test_rules_file_rejects_unknown_keys(tmp_path: object) -> None:
    from pathlib import Path

    path = Path(str(tmp_path)) / "rules.yaml"
    path.write_text("version: 1\nrules:\n  heart_rate: {panic_above: 200}\n")
    with pytest.raises(ValueError, match="panic_above"):
        load_rules(path)
    assert isinstance(default_rules(), RuleSet)
