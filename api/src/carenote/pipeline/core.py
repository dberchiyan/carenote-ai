"""The pipeline as pure functions: match -> redact -> extract -> validate -> flag.

No database here, so the API and the eval runner execute exactly the same code.
"""

import logging
import time
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Literal

from carenote.alerts.rules import Flag, RuleSet, default_rules
from carenote.contracts.extraction import Extraction
from carenote.contracts.llm import LLMProvider, LLMUsage, Prompt
from carenote.patients.matching import MatchResult, PatientLike, match_patient
from carenote.pipeline.prompts import load_prompt
from carenote.pipeline.redaction import Redaction, redact
from carenote.pipeline.validate import validate_extraction

log = logging.getLogger(__name__)

Step = Literal["transcribe", "match", "redact", "extract", "validate", "flag"]


class PipelineError(Exception):
    def __init__(self, step: Step, message: str) -> None:
        super().__init__(message)
        self.step = step


@dataclass
class PipelineResult:
    match: MatchResult
    redaction: Redaction
    raw_extraction: Extraction
    extraction: Extraction
    flags: dict[str, Flag]
    usage: LLMUsage
    prompt_version: str
    timings_ms: dict[str, int] = field(default_factory=dict)


@contextmanager
def _timed(timings: dict[str, int], step: Step) -> Iterator[None]:
    started = time.perf_counter()
    try:
        yield
    finally:
        timings[step] = round((time.perf_counter() - started) * 1000)
        log.debug("pipeline step %s took %d ms", step, timings[step], extra={"step": step})


def _run[T](step: Step, timings: dict[str, int], fn: Callable[[], T]) -> T:
    with _timed(timings, step):
        try:
            return fn()
        except PipelineError:
            raise
        except Exception as exc:
            log.exception("pipeline step %s failed", step, extra={"step": step})
            raise PipelineError(step, str(exc) or exc.__class__.__name__) from exc


def _hidden_numbers_warning(redaction: Redaction, extraction: Extraction) -> Extraction:
    """If redaction hid anything containing digits, the AI may have missed a value: say so."""
    hidden = [
        placeholder
        for placeholder, original in redaction.mapping.items()
        if not placeholder.startswith("<PATIENT_") and any(c.isdigit() for c in original)
    ]
    if not hidden:
        return extraction
    note = (
        f"Some text was hidden from the AI as personal data ({', '.join(hidden)}). "
        "Check that no value is missing."
    )
    return extraction.model_copy(update={"uncertain": [*extraction.uncertain, note]})


def flag_vitals(extraction: Extraction, rules: RuleSet) -> dict[str, Flag]:
    return {v.kind: rules.flag(v.kind, v.value) for v in extraction.vitals}


def run_text_pipeline(
    transcript: str,
    *,
    ward_patients: Sequence[PatientLike],
    known_patients: Sequence[PatientLike],
    llm: LLMProvider,
    prompt: Prompt | None = None,
    rules: RuleSet | None = None,
    use_ner: bool = True,
) -> PipelineResult:
    """Run every step after transcription. `known_patients` drives redaction (all wards)."""
    prompt = prompt or load_prompt()
    rules = rules or default_rules()
    timings: dict[str, int] = {}

    match = _run("match", timings, lambda: match_patient(transcript, ward_patients))
    redaction = _run("redact", timings, lambda: redact(transcript, known_patients, use_ner=use_ner))
    result = _run("extract", timings, lambda: llm.extract(redaction.text, prompt))
    log.debug(
        "llm %s tokens in=%d out=%d cost=$%.5f latency=%dms",
        result.usage.model,
        result.usage.input_tokens,
        result.usage.output_tokens,
        result.usage.cost_usd,
        result.usage.latency_ms,
        extra={"step": "extract", "model": result.usage.model},
    )
    extraction = _run(
        "validate",
        timings,
        lambda: _hidden_numbers_warning(redaction, validate_extraction(result.extraction)),
    )
    flags = _run("flag", timings, lambda: flag_vitals(extraction, rules))
    return PipelineResult(
        match=match,
        redaction=redaction,
        raw_extraction=result.extraction,
        extraction=extraction,
        flags=flags,
        usage=result.usage,
        prompt_version=prompt.version,
        timings_ms=timings,
    )
