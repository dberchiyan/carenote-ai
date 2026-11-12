"""Review hints: where the nurse should look twice before confirming. Pure functions.

The draft already carries `uncertain` (what the model doubted) and threshold flags. Hints add two
checks we can do ourselves, for any provider:

- **self_correction** — the value's source span contains a spoken correction ("140 over 85,
  sorry, 145 over 85"). The draft shows the corrected value; the hint shows what was retracted.
- **not_in_transcript** — the value does not appear in its source span or anywhere in the
  transcript, even after reading number words and unit conversions. An LLM that invents or
  misreads a number is the dangerous failure: the field looks plausible.
"""

import re
from typing import Literal

from pydantic import BaseModel

from carenote.clinical.speech import CORRECTION_MARKER, SPOKEN_VALUE, spoken_to_digits
from carenote.clinical.vitals import VitalKind
from carenote.contracts.extraction import Extraction, Vital
from carenote.pipeline.validate import normalize_unit

HintReason = Literal["self_correction", "not_in_transcript"]

_MARKER = re.compile(CORRECTION_MARKER, re.IGNORECASE)
_VALUE = re.compile(SPOKEN_VALUE, re.IGNORECASE)
_NUMBER = re.compile(r"\d+(?:\.\d+)?")
# Units a value may have been spoken in before we normalised it to UCUM.
_SPOKEN_UNITS: dict[str, tuple[str, ...]] = {
    "temperature": ("F",),
    "weight": ("lb",),
    "blood_glucose": ("mmol/L",),
}


class ReviewHint(BaseModel):
    kind: VitalKind
    reason: HintReason
    message: str
    retracted_value: float | None = None


def _fmt(value: float) -> str:
    return f"{value:g}"


def _retracted(vital: Vital) -> float | None:
    """The value said before the correction marker, if the span holds one."""
    text = spoken_to_digits(vital.source_text)
    marker = _MARKER.search(text)
    if marker is None:
        return None
    before = list(_VALUE.finditer(text[: marker.start()]))
    if not before:
        return None
    numbers = [float(n) for n in _NUMBER.findall(before[-1].group(0))]
    if vital.kind == "diastolic_bp":
        return numbers[1] if len(numbers) > 1 else None
    return numbers[0]


def _appears(vital: Vital, text: str) -> bool:
    for raw in _NUMBER.findall(spoken_to_digits(text)):
        n = float(raw)
        if abs(n - vital.value) <= 0.05:
            return True
        for unit in _SPOKEN_UNITS.get(vital.kind, ()):
            if abs(normalize_unit(vital.kind, n, unit)[0] - vital.value) <= 0.05:
                return True
    return False


def review_hints(extraction: Extraction, transcript: str) -> list[ReviewHint]:
    hints: list[ReviewHint] = []
    for vital in extraction.vitals:
        retracted = _retracted(vital)
        if retracted is not None and abs(retracted - vital.value) > 0.05:
            hints.append(
                ReviewHint(
                    kind=vital.kind,
                    reason="self_correction",
                    message=f"Corrected while dictating: {_fmt(retracted)} → {_fmt(vital.value)}",
                    retracted_value=retracted,
                )
            )
        if not _appears(vital, vital.source_text) and not _appears(vital, transcript):
            hints.append(
                ReviewHint(
                    kind=vital.kind,
                    reason="not_in_transcript",
                    message=f"{_fmt(vital.value)} was not found in the dictation",
                )
            )
    return hints
