"""Fake providers: no network, no API keys, deterministic. Used in tests, CI and the keyless demo.

`RuleBasedLLM` is a real (if simple) extractor built from regular expressions. It doubles as the
baseline in the evaluation report, so LLM providers are compared against something honest.
"""

import hashlib
import re
from collections.abc import Callable
from dataclasses import dataclass

from carenote.clinical.speech import CORRECTION_MARKER as _MARKER
from carenote.clinical.speech import NUMBER_WORDS as _NUMBER_WORDS
from carenote.clinical.speech import SPOKEN_VALUE as _VALUE
from carenote.clinical.speech import words_to_number
from carenote.clinical.vitals import VitalKind
from carenote.clinical.vocabulary import MEDICATIONS, ROUTES, SYMPTOMS
from carenote.contracts.extraction import Extraction, Medication, Vital
from carenote.contracts.llm import (
    ExtractionResult,
    LLMUsage,
    Prompt,
    TranscriptionResult,
)

RULE_BASED_MODEL = "rule-based-v1"

# --- Text rewriting with an offset map back to the original ------------------------------------


class Rewriter:
    """Applies regex substitutions while remembering where each output char came from."""

    def __init__(self, text: str) -> None:
        self.original = text
        self.text = text
        self.starts = list(range(len(text)))
        self.ends = list(range(1, len(text) + 1))

    def sub(self, pattern: re.Pattern[str], repl: Callable[[re.Match[str]], str]) -> None:
        out: list[str] = []
        starts: list[int] = []
        ends: list[int] = []
        last = 0
        for m in pattern.finditer(self.text):
            out.append(self.text[last : m.start()])
            starts += self.starts[last : m.start()]
            ends += self.ends[last : m.start()]
            replacement = repl(m)
            orig_start, orig_end = self.starts[m.start()], self.ends[m.end() - 1]
            out.append(replacement)
            starts += [orig_start] * len(replacement)
            ends += [orig_end] * len(replacement)
            last = m.end()
        out.append(self.text[last:])
        starts += self.starts[last:]
        ends += self.ends[last:]
        self.text, self.starts, self.ends = "".join(out), starts, ends

    def source(self, start: int, end: int) -> str:
        return self.original[self.starts[start] : self.ends[end - 1]].strip(" ,.")


# --- Patterns ---------------------------------------------------------------------------------

_N = r"(\d{1,4}(?:\.\d+)?)"
# Speech-to-text punctuates dictation ("pulse, 80", "temperature: 37.9"): allow it.
_LINK = r"(?:[\s,:]+(?:is|was|of|at))?[\s,:]*"
_UNIT_WORDS = (
    r"(?:%|percent|bpm|per\s+minute|on\s+room\s+air|on\s+ra|ra|degrees|kg|kilos|kilograms|mg/dl)"
)
# A spoken self-correction: <value> <marker(s)> [<vital label>] <value>. A value may be a
# blood-pressure pair, so "140 over 85, sorry, 145 over 85" replaces the whole reading. Markers
# can be chained ("sorry, correction,"); a bare "no"/"sorry" only counts when followed by a comma.
_VITAL_LABEL = (
    r"(?:blood\s+pressure|bp|pulse|heart\s+rate|hr|temperature|temp|sats|spo2|saturation"
    r"|resp(?:iratory)?\s+rate|rr|it'?s|it\s+was|was|is)"
)
_CORRECTION = re.compile(
    rf"(?<![\d.])({_VALUE})((?:\s*{_UNIT_WORDS})*)\s*(?:\.\.\.|…)?\s*,?\s*"
    rf"{_MARKER}(?:\s*,?\s*{_MARKER})*\s*,?\s*"
    rf"((?:{_VITAL_LABEL}\s+)*)({_VALUE})",
    re.IGNORECASE,
)  # groups: retracted value, its unit words, label repeated after the marker, corrected value
_BP = re.compile(rf"\b(?:blood\s+pressure|bp){_LINK}{_N}\s*(?:/|over)\s*{_N}", re.IGNORECASE)
_SINGLE: tuple[tuple[VitalKind, re.Pattern[str], str], ...] = (
    (
        "heart_rate",
        re.compile(rf"\b(?:pulse|heart\s+rate|hr|p){_LINK}{_N}(?:\s*bpm)?", re.I),
        "/min",
    ),
    (
        "respiratory_rate",
        re.compile(
            rf"\b(?:respiratory\s+rate|resp(?:iratory)?\s+rate|resps|respirations|rr|breathing)"
            rf"{_LINK}{_N}(?:\s*(?:per\s+minute|/min))?",
            re.I,
        ),
        "/min",
    ),
    (
        "temperature",
        re.compile(
            rf"\b(?:temperature|temp|t){_LINK}{_N}(?:\s*(?:degrees|°)?\s*(c|f)\b)?(?:\s*degrees)?",
            re.I,
        ),
        "Cel",
    ),
    (
        "spo2",
        re.compile(
            rf"\b(?:oxygen\s+saturation|saturation|saturating|sats|spo2|o2\s+sats?){_LINK}{_N}\s*(?:%|percent)?",
            re.I,
        ),
        "%",
    ),
    (
        "weight",
        re.compile(rf"\b(?:weight|weighs|wt){_LINK}{_N}\s*(kg|kilos|kilograms|lbs?|pounds)?", re.I),
        "kg",
    ),
    (
        "blood_glucose",
        re.compile(
            rf"\b(?:blood\s+sugar|blood\s+glucose|glucose|sugar|bg|bm){_LINK}{_N}\s*(mg/dl|mmol(?:/l)?)?",
            re.I,
        ),
        "mg/dL",
    ),
)
# The same vitals with the value spoken first: "38 temperature", "88 pulse", "94 percent sats".
# Blood pressure is left out: "150 over 90 BP" is rare and "over" already anchors the pair.
_REVERSED: tuple[tuple[VitalKind, re.Pattern[str], str], ...] = (
    (
        "heart_rate",
        re.compile(rf"(?<![\d.]){_N}[\s,]*(?:bpm[\s,]*)?(?:pulse|heart\s+rate|hr)\b", re.I),
        "/min",
    ),
    (
        "respiratory_rate",
        re.compile(
            rf"(?<![\d.]){_N}[\s,]*(?:breaths\s*(?:per\s+minute|/min)?\s*)?"
            rf"(?:respiratory\s+rate|resp(?:iratory)?\s+rate|resps|respirations|rr)\b",
            re.I,
        ),
        "/min",
    ),
    (
        "temperature",
        re.compile(
            rf"(?<![\d.]){_N}[\s,]*(?:degrees|°)?\s*(c|f)?\b[\s,]*(?:temperature|temp)\b", re.I
        ),
        "Cel",
    ),
    (
        "spo2",
        re.compile(
            rf"(?<![\d.]){_N}[\s,]*(?:%|percent)?[\s,]*(?:oxygen\s+saturation|saturation|sats|spo2|o2\s+sats?)\b",
            re.I,
        ),
        "%",
    ),
)
_VALUE_FIRST = frozenset(pattern for _, pattern, _ in _REVERSED)
# Every label and unit word the label-first patterns know, so "T 37.8, sats 94" keeps 37.8 with T.
_ANY_LABEL = (
    r"(?:blood\s+pressure|bp|pulse|heart\s+rate|hr|p|respiratory\s+rate|resp(?:iratory)?\s+rate"
    r"|resps|respirations|rr|breathing|temperature|temp|t|oxygen\s+saturation|saturation"
    r"|saturating|sats|spo2|o2\s+sats?|weight|weighs|wt|blood\s+sugar|blood\s+glucose|glucose"
    r"|sugar|bg|bm|degrees|°|c|f|%|percent|bpm|/min|per\s+minute|on\s+room\s+air|on\s+ra|ra"
    r"|mmhg|kg|kilos|kilograms|mg/dl|mmol(?:/l)?)"
)
# "sugar is 313, pulse 59": the linking word belongs to the label; "128 over 76, pulse" keeps
# 76 with the pressure pair.
_LABEL_THEN_SEP = re.compile(
    rf"(?:^|\W)(?:{_ANY_LABEL}(?:[\s,:]+(?:is|was|of|at))?|over|/)(?P<sep>[\s,:]*)$",
    re.IGNORECASE,
)


def _value_belongs_to_next_label(text: str, m: re.Match[str]) -> bool:
    """For a value-first match, is the number really for the label after it, or does it belong
    to a label before it? Not preceded by a label: yes. Preceded by one: only when a comma
    separates the previous label from the number and none separates the number from ours."""
    previous = _LABEL_THEN_SEP.search(text[: m.start()])
    if previous is None:
        return True
    comma_before = "," in previous.group("sep")
    comma_after = "," in m.group(0)[len(m.group(1)) :]
    return comma_before and not comma_after


_MISSING = re.compile(
    r"[^.,;]*\b(?:not\s+(?:taken|recorded|done|checked|counted)|couldn't\s+get|no\s+\w+\s+reading)[^.,;]*",
    re.IGNORECASE,
)
_NEGATION = re.compile(r"\b(?:no|denies|denied|without|not)\b[^.;]*$", re.IGNORECASE)
_DOSE = re.compile(
    r"(\d+(?:\.\d+)?)\s*(mg|milligrams?|g|grams?|mcg|units?|puffs?)\b", re.IGNORECASE
)
_PATIENT = re.compile(r"<PATIENT_\d+>")


def _sentence_bounds(text: str, index: int) -> tuple[int, int]:
    start = max(text.rfind(". ", 0, index), text.rfind("; ", 0, index))
    end_candidates = [i for i in (text.find(". ", index), text.find("; ", index)) if i != -1]
    return (start + 2 if start != -1 else 0), (min(end_candidates) if end_candidates else len(text))


@dataclass
class _Found:
    start: int
    vital: Vital


def rule_based_extract(text: str) -> Extraction:
    rw = Rewriter(text)
    rw.sub(_NUMBER_WORDS, lambda m: words_to_number(m.group(0)))
    rw.sub(_CORRECTION, lambda m: m.group(3) + m.group(4) + m.group(2))
    t = rw.text

    found: list[_Found] = []
    taken: list[tuple[int, int]] = []
    for m in _BP.finditer(t):
        src = rw.source(m.start(), m.end())
        found.append(
            _Found(
                m.start(),
                Vital(kind="systolic_bp", value=float(m.group(1)), unit="mm[Hg]", source_text=src),
            )
        )
        found.append(
            _Found(
                m.start(),
                Vital(kind="diastolic_bp", value=float(m.group(2)), unit="mm[Hg]", source_text=src),
            )
        )
        taken.append((m.start(), m.end()))
    # Value-first readings ("80 pulse") are claimed before label-first ones ("pulse 80"), with
    # one rule for a number sitting between two labels: "temperature, 88 pulse" gives 88 to
    # pulse (comma before, none after); "pulse, 80, temperature" and "pulse 88 temperature"
    # give it to the label before it.
    for kind, pattern, default_unit in (*_REVERSED, *_SINGLE):
        for m in pattern.finditer(t):
            if any(s < m.end() and m.start() < e for s, e in taken):
                continue
            if pattern in _VALUE_FIRST and not _value_belongs_to_next_label(t, m):
                continue
            unit = (m.group(2) if m.lastindex and m.lastindex >= 2 else None) or default_unit
            found.append(
                _Found(
                    m.start(),
                    Vital(
                        kind=kind,
                        value=float(m.group(1)),
                        unit=unit,
                        source_text=rw.source(m.start(), m.end()),
                    ),
                )
            )
            taken.append((m.start(), m.end()))
    vitals = [f.vital for f in sorted(found, key=lambda f: f.start)]

    lowered = t.lower()
    symptoms: list[str] = []
    for canonical, phrases in SYMPTOMS.items():
        for phrase in sorted(phrases, key=len, reverse=True):
            hit = re.search(rf"\b{re.escape(phrase)}\b", lowered)
            if hit is None:
                continue
            clause_start = max(lowered.rfind(c, 0, hit.start()) for c in ".;,")
            if not _NEGATION.search(lowered[clause_start + 1 : hit.start()]):
                symptoms.append(canonical)
            break

    medications: list[Medication] = []
    for name in MEDICATIONS:
        mention = re.search(rf"\b{re.escape(name)}\b", lowered)
        if mention is None:
            continue
        s, e = _sentence_bounds(lowered, mention.start())
        sentence = t[s:e]
        doses = list(_DOSE.finditer(sentence))
        dose = None
        if doses:
            nearest = min(doses, key=lambda d: abs(d.start() + s - mention.start()))
            dose = f"{nearest.group(1)} {nearest.group(2)}"
        route = next(
            (
                canonical
                for canonical, phrases in ROUTES.items()
                for p in phrases
                if re.search(rf"(?<![\w.]){re.escape(p)}(?![\w])", sentence, re.IGNORECASE)
            ),
            None,
        )
        medications.append(
            Medication(name=name, dose=dose, route=route, source_text=rw.source(s, e))
        )

    uncertain = [f"Not recorded: {m.group(0).strip()}" for m in _MISSING.finditer(t)]
    patients = list(dict.fromkeys(_PATIENT.findall(text)))
    if len(patients) > 1:
        uncertain.append(f"More than one patient mentioned ({', '.join(patients)}).")

    return Extraction(
        patient_mention=patients[0] if patients else None,
        vitals=vitals,
        symptoms=symptoms,
        medications=medications,
        free_text_summary=_summary(vitals, symptoms, medications),
        uncertain=uncertain,
    )


def _summary(vitals: list[Vital], symptoms: list[str], medications: list[Medication]) -> str:
    parts = []
    if vitals:
        parts.append(f"{len(vitals)} vital sign value{'s' if len(vitals) != 1 else ''} recorded")
    if symptoms:
        parts.append("reports " + ", ".join(symptoms))
    if medications:
        parts.append("given " + ", ".join(m.name for m in medications))
    return (("; ".join(parts) + ".").capitalize()) if parts else "No structured findings."


class RuleBasedLLM:
    """Stands in for an LLM: same interface, deterministic, zero cost.

    Token counts are an estimate (characters / 4) so the metrics page has something to show
    in the keyless demo; the cost is genuinely $0. With `record=True` every text "sent" is kept
    for inspection (the redaction leak test); the runtime instance never records, since it is
    a cached singleton that would otherwise grow for the life of the process.
    """

    name = "fake"

    def __init__(self, record: bool = False) -> None:
        self.record = record
        self.requests: list[str] = []

    def extract(self, redacted_text: str, prompt: Prompt) -> ExtractionResult:
        if self.record:
            self.requests.append(prompt.system + "\n" + redacted_text)
        extraction = rule_based_extract(redacted_text)
        return ExtractionResult(
            extraction=extraction,
            usage=LLMUsage(
                model=RULE_BASED_MODEL,
                input_tokens=(len(prompt.system) + len(redacted_text)) // 4,
                output_tokens=len(extraction.model_dump_json()) // 4,
                cost_usd=0.0,
                latency_ms=0,
            ),
        )


DEMO_TRANSCRIPT = (
    "Mrs. Anna Keller, blood pressure 150 over 90, pulse 88, temperature 37.9. "
    "Complains of a headache. Gave 500 mg paracetamol orally."
)


class FakeTranscription:
    """Returns a known transcript for registered audio (by SHA-256), else a fixed demo note."""

    name = "fake"

    def __init__(self, known: dict[str, str] | None = None, default: str = DEMO_TRANSCRIPT) -> None:
        self.known = known or {}
        self.default = default

    @staticmethod
    def digest(audio: bytes) -> str:
        return hashlib.sha256(audio).hexdigest()

    def transcribe(
        self, audio: bytes, filename: str, content_type: str, duration_s: float | None = None
    ) -> TranscriptionResult:
        text = self.known.get(self.digest(audio), self.default)
        return TranscriptionResult(text=text, model="fake-transcriber", latency_ms=0, cost_usd=0.0)
