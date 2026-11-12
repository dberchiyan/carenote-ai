"""Local patient matching. Runs before anything leaves the system (no LLM involved).

Each patient is scored by fuzzy-matching their name against word windows of the transcript:
the full name, the family name right after a title (Mr./Mrs./Ms.), or, weakest, the given name
alone, optionally confirmed by the room number. A single clear winner is auto-selected; a
first-name-only hit is only ever offered as a candidate; anything else needs the nurse to pick.
"""

import re
import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from itertools import pairwise
from typing import Literal, Protocol

from rapidfuzz import fuzz

MATCH_THRESHOLD = 88.0
CANDIDATE_FLOOR = 70.0
# A single name on its own ("John, pulse 88", "Smith, 80") is offered, never auto-selected.
GIVEN_NAME_CAP = 80.0
# Two candidates for the *same* words (e.g. "Anna Keller" vs "Hanna Keller") need this lead.
SAME_SPAN_MARGIN = 3.0
TITLES = {"mr", "mrs", "ms", "miss", "mister", "missus"}


class PatientLike(Protocol):
    @property
    def id(self) -> uuid.UUID: ...
    @property
    def given_name(self) -> str: ...
    @property
    def family_name(self) -> str: ...
    @property
    def room(self) -> str: ...


@dataclass(frozen=True)
class Candidate:
    patient_id: uuid.UUID
    score: float
    matched_text: str
    span: tuple[int, int]  # token indices [start, end)


@dataclass(frozen=True)
class MatchResult:
    status: Literal["matched", "ambiguous", "none"]
    selected_id: uuid.UUID | None
    candidates: list[Candidate] = field(default_factory=list)


_TOKEN = re.compile(r"[A-Za-z0-9]+(?:['-][A-Za-z]+)*")


def _tokens(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN.findall(text)]


def _best_window(tokens: list[str], target: list[str]) -> tuple[float, tuple[int, int]]:
    n = len(target)
    phrase = " ".join(target)
    best, span = 0.0, (0, 0)
    for i in range(len(tokens) - n + 1):
        score = fuzz.ratio(" ".join(tokens[i : i + n]), phrase)
        if score > best:
            best, span = score, (i, i + n)
    return best, span


def _room_mentioned(tokens: list[str], room: str) -> bool:
    room = room.lower()
    joined = [*tokens, *(a + b for a, b in pairwise(tokens))]
    return room in joined


def _score(tokens: list[str], patient: PatientLike) -> Candidate | None:
    full = _tokens(f"{patient.given_name} {patient.family_name}")
    family = _tokens(patient.family_name)
    full_score, full_span = _best_window(tokens, full)

    family_score, family_span = 0.0, (0, 0)
    for i in range(1, len(tokens) - len(family) + 1):
        if tokens[i - 1] in TITLES:
            score = fuzz.ratio(" ".join(tokens[i : i + len(family)]), " ".join(family))
            if score > family_score:
                family_score, family_span = score, (i - 1, i + len(family))
    family_score *= 0.95  # less specific than a full name

    # One name on its own ("John, pulse 88", "Smith, 80, pulse"): offered, never auto-selected.
    bare: list[tuple[float, tuple[int, int]]] = []
    for name in (_tokens(patient.given_name), family):
        name_score, name_span = _best_window(tokens, name)
        if name_score >= MATCH_THRESHOLD:
            bare.append((min(name_score, GIVEN_NAME_CAP), name_span))

    score, span = max(
        ((full_score, full_span), (family_score, family_span), *bare),
        key=lambda pair: pair[0],
    )
    if _room_mentioned(tokens, patient.room) and score >= CANDIDATE_FLOOR:
        score = min(100.0, score + 8)
    if score < CANDIDATE_FLOOR:
        return None
    return Candidate(patient.id, round(score, 1), " ".join(tokens[span[0] : span[1]]), span)


def _overlaps(a: tuple[int, int], b: tuple[int, int]) -> bool:
    return a[0] < b[1] and b[0] < a[1]


def match_patient(transcript: str, patients: Sequence[PatientLike]) -> MatchResult:
    tokens = _tokens(transcript)
    candidates = sorted(
        (c for p in patients if (c := _score(tokens, p)) is not None),
        key=lambda c: c.score,
        reverse=True,
    )
    strong = [c for c in candidates if c.score >= MATCH_THRESHOLD]
    if not strong:
        return MatchResult("none", None, candidates)
    best, rivals = strong[0], strong[1:]
    for rival in rivals:
        # A rival on different words is a second patient mentioned in the note; a rival on the
        # same words is a near-identical name that only wins if clearly behind.
        if not _overlaps(best.span, rival.span) or best.score - rival.score < SAME_SPAN_MARGIN:
            return MatchResult("ambiguous", None, candidates)
    return MatchResult("matched", best.patient_id, candidates)
