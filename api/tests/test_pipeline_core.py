import pytest

from carenote.contracts.llm import ExtractionResult, Prompt, ProviderError
from carenote.patients.synthetic import generate_patients
from carenote.pipeline.core import PipelineError, run_text_pipeline
from carenote.providers.fake import RuleBasedLLM

PATIENTS = generate_patients()
WARD_A = [p for p in PATIENTS if p.ward == "3A"]


def test_end_to_end_text_pipeline_with_fake_provider() -> None:
    result = run_text_pipeline(
        "Mrs. Anna Keller, blood pressure 150 over 90, pulse 88, complains of a headache, "
        "gave 500 mg paracetamol orally.",
        ward_patients=WARD_A,
        known_patients=PATIENTS,
        llm=RuleBasedLLM(),
    )
    assert result.match.status == "matched"
    assert result.redaction.text.startswith("<PATIENT_1>,")
    assert result.extraction.patient_mention == "<PATIENT_1>"
    assert result.flags == {
        "systolic_bp": "warning",
        "diastolic_bp": "normal",
        "heart_rate": "normal",
    }
    assert result.extraction.symptoms == ["headache"]
    assert result.extraction.medications[0].dose == "500 mg"
    assert result.prompt_version == "extract_v1"
    assert set(result.timings_ms) == {"match", "redact", "extract", "validate", "flag"}


class FailingLLM:
    name = "failing"

    def extract(self, redacted_text: str, prompt: Prompt) -> ExtractionResult:
        raise ProviderError("Anthropic API error 529: overloaded")


def test_provider_failure_is_reported_with_its_step() -> None:
    with pytest.raises(PipelineError) as info:
        run_text_pipeline(
            "Pulse 80", ward_patients=WARD_A, known_patients=PATIENTS, llm=FailingLLM()
        )
    assert info.value.step == "extract"
    assert "overloaded" in str(info.value)


def test_hidden_digits_are_surfaced_to_the_nurse() -> None:
    result = run_text_pipeline(
        "Mrs. Anna Keller, pulse 80. Daughter called from 0151 2345678.",
        ward_patients=WARD_A,
        known_patients=PATIENTS,
        llm=RuleBasedLLM(),
    )
    assert any("<PHONE_1>" in u for u in result.extraction.uncertain)
