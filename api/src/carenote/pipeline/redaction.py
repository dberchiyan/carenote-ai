"""PII redaction. Only the redacted text may leave the system.

Two passes:
1. Known patient names (from our own database) -> <PATIENT_n>, one placeholder per patient.
2. Presidio NER for anything else -> <PERSON_n>, <DATE_n>, <PHONE_n>, <EMAIL_n>, <LOCATION_n>.

The placeholder -> original mapping stays server-side (stored on the note, never sent out).
"""

import logging
import re
import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from functools import cache
from typing import TYPE_CHECKING

from carenote.clinical.vocabulary import MEDICATIONS, ROUTES, SYMPTOMS
from carenote.patients.matching import TITLES, PatientLike

if TYPE_CHECKING:
    from presidio_analyzer import AnalyzerEngine

PRESIDIO_ENTITIES = {
    "PERSON": "PERSON",
    "PHONE_NUMBER": "PHONE",
    "EMAIL_ADDRESS": "EMAIL",
    "DATE_TIME": "DATE",
    "LOCATION": "LOCATION",
}
MIN_SCORE = 0.35

# Words that Presidio sometimes tags as names or places in clinical shorthand.
_CLINICAL_TERMS = (
    {m.lower() for m in MEDICATIONS}
    | {p for phrases in SYMPTOMS.values() for p in phrases}
    | {p for phrases in ROUTES.values() for p in phrases}
    | {"bp", "hr", "rr", "ra", "sats", "spo2", "bg", "bm", "temp", "bpm", "stat", "b.i.d.", "prn"}
    # Vital-sign words: Presidio has tagged "Sugar" as a LOCATION, hiding the value's context.
    | {
        "sugar", "glucose", "pulse", "temperature", "saturation", "saturating", "oxygen",
        "weight", "weighs", "wt", "resps", "respirations", "breathing", "pressure", "blood",
        "heart", "rate", "kilos", "kilograms", "percent", "degrees", "room", "air",
    }
)  # fmt: skip
_MONTHS = (
    "january|february|march|april|may|june|july|august|september|october|november|december"
    "|jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec"
)
# Times of day ("14:00") are not identifying; dates and birthdays are.
_DATE_WORDS = re.compile(
    rf"\b({_MONTHS})\b|\b(19|20)\d{{2}}\b"
    r"|\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday|birthday|born)\b",
    re.IGNORECASE,
)
_NUMERIC_DATE = re.compile(r"\b(\d{1,2})[./-](\d{1,2})(?:[./-]\d{2,4})?\b")


def _looks_like_date(span: str) -> bool:
    """True for "12 March", "1987" or "03/04"; false for blood pressures such as "98/60"."""
    if _DATE_WORDS.search(span):
        return True
    for m in _NUMERIC_DATE.finditer(span):
        a, b = int(m.group(1)), int(m.group(2))
        if (1 <= a <= 31 and 1 <= b <= 12) or (1 <= a <= 12 and 1 <= b <= 31):
            return True
    return False


_PLACEHOLDER = re.compile(r"<[A-Z]+_\d+>")


@dataclass
class Redaction:
    text: str
    mapping: dict[str, str] = field(default_factory=dict)  # placeholder -> original text
    patient_placeholders: dict[str, uuid.UUID] = field(default_factory=dict)


@cache
def _analyzer() -> "AnalyzerEngine":
    from presidio_analyzer import AnalyzerEngine
    from presidio_analyzer.nlp_engine import NlpEngineProvider

    logging.getLogger("presidio-analyzer").setLevel(logging.ERROR)
    provider = NlpEngineProvider(
        nlp_configuration={
            "nlp_engine_name": "spacy",
            "models": [{"lang_code": "en", "model_name": "en_core_web_sm"}],
            "ner_model_configuration": {
                "labels_to_ignore": ["CARDINAL", "ORDINAL", "QUANTITY", "PERCENT", "MONEY"]
            },
        }
    )
    return AnalyzerEngine(nlp_engine=provider.create_engine(), supported_languages=["en"])


def warm_up() -> None:
    """Load the NLP model ahead of the first request."""
    _analyzer()


def _name_patterns(
    patients: Sequence[PatientLike],
) -> list[tuple[re.Pattern[str], list[uuid.UUID]]]:
    """Regexes for full names, title + family name, family names and given names.

    Longest first, so "Mrs. Anna Keller" is replaced as one unit. A pattern can belong to several
    patients (two Kellers): the mention is then attributed to whichever is already in the note.
    """
    titles = "|".join(sorted(TITLES, key=len, reverse=True))
    title = rf"(?:(?:{titles})\.?\s+)?"
    by_pattern: dict[str, list[uuid.UUID]] = {}
    for p in patients:
        given, family = re.escape(p.given_name), re.escape(p.family_name)
        for pattern in (rf"{title}{given}\s+{family}", rf"{title}{family}", given):
            by_pattern.setdefault(pattern, []).append(p.id)
    ordered = sorted(by_pattern.items(), key=lambda kv: len(kv[0]), reverse=True)
    return [(re.compile(rf"\b{pat}\b", re.IGNORECASE), ids) for pat, ids in ordered]


def redact(text: str, patients: Sequence[PatientLike], use_ner: bool = True) -> Redaction:
    """Redact `text`. `patients` should be every patient we know, not only the ward's."""
    result = Redaction(text=text)
    by_patient: dict[uuid.UUID, str] = {}

    def placeholder_for(ids: list[uuid.UUID], original: str) -> str:
        known = [pid for pid in ids if pid in by_patient]
        if known:
            return by_patient[known[0]]
        token = f"<PATIENT_{len(set(by_patient.values())) + 1}>"
        for pid in ids:
            by_patient[pid] = token
        if len(ids) == 1:  # ambiguous mentions are not attributed to a specific patient
            result.patient_placeholders[token] = ids[0]
        result.mapping[token] = original
        return token

    # Collect every name mention first (longest patterns win overlaps), then number placeholders
    # in order of appearance.
    spans: list[tuple[int, int, list[uuid.UUID]]] = []
    for pattern, ids in _name_patterns(patients):
        for m in pattern.finditer(text):
            if all(m.end() <= s or m.start() >= e for s, e, _ in spans):
                spans.append((m.start(), m.end(), ids))
    spans.sort()
    # Attribute ambiguous mentions (two Kellers) to a patient already named in the note.
    unique_first = sorted(spans, key=lambda s: len(s[2]) > 1)
    tokens = {start: placeholder_for(ids, text[start:end]) for start, end, ids in unique_first}
    # Renumber by position.
    order: dict[str, str] = {}
    for start, _, _ in spans:
        order.setdefault(tokens[start], f"<PATIENT_{len(order) + 1}>")
    result.mapping = {order[k]: v for k, v in result.mapping.items()}
    result.patient_placeholders = {order[k]: v for k, v in result.patient_placeholders.items()}
    redacted = text
    for start, end, _ in reversed(spans):
        redacted = redacted[:start] + order[tokens[start]] + redacted[end:]
    result.text = _redact_ner(redacted, result) if use_ner else redacted
    return result


def _redact_ner(text: str, result: Redaction) -> str:
    findings = [
        r
        for r in _analyzer().analyze(
            text, language="en", entities=list(PRESIDIO_ENTITIES), score_threshold=MIN_SCORE
        )
        if _keep(r.entity_type, text[r.start : r.end])
    ]
    # Prefer longer, then higher-scoring spans; drop overlaps (phone numbers also look like dates).
    findings.sort(key=lambda r: (-(r.end - r.start), -r.score))
    chosen: list[tuple[int, int, str]] = []
    for r in findings:
        if all(r.end <= s or r.start >= e for s, e, _ in chosen):
            chosen.append((r.start, r.end, r.entity_type))

    counters: dict[str, int] = {}
    seen: dict[tuple[str, str], str] = {}
    for start, end, entity in sorted(chosen, reverse=True):
        original = text[start:end]
        label = PRESIDIO_ENTITIES[entity]
        key = (label, original.lower())
        if key not in seen:
            counters[label] = counters.get(label, 0) + 1
            seen[key] = f"<{label}_{counters[label]}>"
            result.mapping[seen[key]] = original
        text = text[:start] + seen[key] + text[end:]
    # Numbering was assigned right-to-left; renumber left-to-right for readability.
    return _renumber(text, result)


def _keep(entity: str, span: str) -> bool:
    lowered = span.lower().strip(" .,")
    if _PLACEHOLDER.search(span):
        return False
    if any(term in lowered.split() or term == lowered for term in _CLINICAL_TERMS):
        return False
    if any(word in _CLINICAL_TERMS for word in re.findall(r"[a-z0-9.]+", lowered)):
        return False
    if entity == "DATE_TIME":
        return _looks_like_date(span)
    if entity == "PHONE_NUMBER":
        # Vitals like "168/96" or "37.8" must never be mistaken for phone numbers.
        return sum(c.isdigit() for c in span) >= 7
    return not lowered.replace(".", "").isdigit()


def _renumber(text: str, result: Redaction) -> str:
    renamed: dict[str, str] = {}
    counters: dict[str, int] = {}
    for token in _PLACEHOLDER.findall(text):
        label = token[1:-1].rsplit("_", 1)[0]
        if label == "PATIENT" or token in renamed:
            continue
        counters[label] = counters.get(label, 0) + 1
        renamed[token] = f"<{label}_{counters[label]}#>"
    for old, new in renamed.items():
        text = text.replace(old, new)
    mapping = {k: v for k, v in result.mapping.items() if k not in renamed}
    mapping |= {new.replace("#", ""): result.mapping[old] for old, new in renamed.items()}
    result.mapping = mapping
    return text.replace("#>", ">")


def unredact(text: str, mapping: dict[str, str]) -> str:
    return _PLACEHOLDER.sub(lambda m: mapping.get(m.group(0), m.group(0)), text)


_TITLE = re.compile(r"^(?:Mr|Mrs|Ms|Miss|Mx|Dr)\.?\s+", re.IGNORECASE)


def _name_variants(original: str) -> list[str]:
    """ "Mrs. Anna Keller" -> itself, "Anna Keller", "Anna", "Keller". Longest first."""
    bare = _TITLE.sub("", original).strip()
    words = [w for w in re.split(r"[\s,]+", bare) if len(w) >= 3]
    variants = {original, bare, *words}
    return sorted((v for v in variants if v), key=len, reverse=True)


def reredact(text: str, mapping: dict[str, str]) -> str:
    """Inverse of `unredact`: put placeholders back wherever an original span, or a name from it,
    appears. Longest first, so "Anna Keller" wins over "Keller". Used before storing anything
    that came back from the browser, where the nurse saw real words.
    """
    candidates = [
        (variant, placeholder)
        for placeholder, original in mapping.items()
        for variant in _name_variants(original)
    ]
    for variant, placeholder in sorted(candidates, key=lambda c: -len(c[0])):
        text = text.replace(variant, placeholder)
    return text
