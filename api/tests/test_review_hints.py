from carenote.contracts.extraction import Extraction, Vital
from carenote.pipeline.review_hints import review_hints
from carenote.providers.fake import rule_based_extract


def _extraction(*vitals: Vital) -> Extraction:
    return Extraction(
        patient_mention=None,
        vitals=list(vitals),
        symptoms=[],
        medications=[],
        free_text_summary="",
        uncertain=[],
    )


def test_a_spoken_bp_correction_shows_the_retracted_value() -> None:
    text = "Mr. John Smith, pulse 72, BP 140 over 85, sorry, correction, 145 over 85."
    hints = review_hints(rule_based_extract(text), text)
    assert [(h.kind, h.reason, h.retracted_value) for h in hints] == [
        ("systolic_bp", "self_correction", 140)
    ]
    assert hints[0].message == "Corrected while dictating: 140 → 145"


def test_corrections_in_words_and_of_single_values() -> None:
    text = "Irene Hartmann, blood pressure one thirty over eighty, I mean one forty over eighty."
    hints = review_hints(rule_based_extract(text), text)
    assert [(h.kind, h.retracted_value) for h in hints] == [("systolic_bp", 130)]
    text = "temp 37.2, I mean 37.4"
    assert [h.retracted_value for h in review_hints(rule_based_extract(text), text)] == [37.2]


def test_plain_dictation_has_no_hints() -> None:
    text = "Mrs. Anna Keller, blood pressure 150 over 90, pulse 88, temp thirty-seven point nine."
    assert review_hints(rule_based_extract(text), text) == []


def test_a_value_missing_from_the_dictation_is_flagged() -> None:
    # An LLM misreading "pulse 88" as 98 must not look as trustworthy as the real value.
    extraction = _extraction(
        Vital(kind="heart_rate", value=98, unit="/min", source_text="pulse 88"),
    )
    hints = review_hints(extraction, "Anna Keller, pulse 88.")
    assert [(h.kind, h.reason) for h in hints] == [("heart_rate", "not_in_transcript")]
    assert hints[0].message == "98 was not found in the dictation"


def test_unit_conversions_count_as_found() -> None:
    text = "Margaret Neumann, temperature 100.4 F, weight 180 pounds, glucose 7.2 mmol."
    extraction = _extraction(
        Vital(kind="temperature", value=38.0, unit="Cel", source_text="temperature 100.4 F"),
        Vital(kind="weight", value=81.6, unit="kg", source_text="weight 180 pounds"),
        Vital(kind="blood_glucose", value=130, unit="mg/dL", source_text="glucose 7.2 mmol"),
    )
    assert review_hints(extraction, text) == []
