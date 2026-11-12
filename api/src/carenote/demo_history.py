"""A week of synthetic ward history, so the dashboard and trend charts look like a real ward.

Notes are generated as nurse dictations, run through the real text pipeline (rule-based LLM,
so nothing leaves the machine) and confirmed through `notes.service` — the same code path as
the nurse's confirm action. Times follow nursing rounds (morning, afternoon, evening) over
the past days; today only has the rounds that already happened, a couple of them still open
for review. Deterministic for a given `now` and seed. Synthetic data only.
"""

import random
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from carenote.auth.models import User
from carenote.clinical.vitals import VITALS, VitalKind
from carenote.contracts.extraction import Extraction as ExtractionPayload
from carenote.contracts.extraction import Vital
from carenote.notes import service
from carenote.notes.models import (
    ConfirmedObservation,
    Extraction,
    NoteStatus,
    VoiceNote,
)
from carenote.patients.models import Patient
from carenote.pipeline.core import run_text_pipeline
from carenote.providers.fake import RuleBasedLLM

HISTORY_DAYS = 6
# Round start times (UTC) and the chance that a patient is documented in that round.
ROUNDS: tuple[tuple[time, float], ...] = (
    (time(6, 30), 1.0),
    (time(12, 0), 0.45),
    (time(17, 30), 0.7),
)
OPEN_DRAFTS_PER_WARD = {"3A": 3, "3B": 2}
# Authors per ward: (username, share of notes).
AUTHORS: dict[str, tuple[tuple[str, float], ...]] = {
    "3A": (("nurse", 0.7), ("charge", 0.3)),
    "3B": (("nurse_b", 1.0),),
}
SYMPTOM_PHRASES = (
    "complains of a headache",
    "feels dizzy when standing",
    "reports nausea",
    "mild back pain",
    "says she couldn't sleep",
    "a dry cough",
    "tired today",
)
MED_PHRASES = (
    "gave 500 mg paracetamol orally",
    "gave 1 g paracetamol orally",
    "gave 4 mg ondansetron iv",
    "gave 40 mg enoxaparin subcutaneously",
    "gave 25 mg metoprolol orally",
    "gave 400 mg ibuprofen orally",
)


@dataclass
class _Baseline:
    sys: float
    dia: float
    hr: float
    temp: float
    spo2: float
    rr: float
    # Per-day drift; a few patients deteriorate slowly so warning flags appear late in the week.
    sys_trend: float = 0.0
    temp_trend: float = 0.0
    spo2_trend: float = 0.0


def _baseline(rng: random.Random, deteriorating: bool) -> _Baseline:
    b = _Baseline(
        sys=rng.uniform(112, 136),
        dia=rng.uniform(68, 84),
        hr=rng.uniform(62, 88),
        temp=rng.uniform(36.4, 37.1),
        spo2=rng.uniform(95, 99),
        rr=rng.uniform(13, 18),
    )
    if deteriorating:
        b.sys_trend = rng.uniform(3, 5)
        b.temp_trend = rng.uniform(0.15, 0.25)
        b.spo2_trend = -rng.uniform(0.3, 0.6)
    return b


def _dictation(
    rng: random.Random, p: Patient, b: _Baseline, day_index: int, correction: bool = False
) -> tuple[str, dict[VitalKind, float]]:
    """A dictation and the values the nurse meant. Some phrasings are colloquial ("BP's 132 on
    78", "oxygen 94 percent"): the rule-based extractor genuinely misses them, so the nurse has
    to fix the draft, which is what the AI quality page measures."""
    title = "Mrs." if p.sex == "female" else "Mr."
    sys = round(b.sys + b.sys_trend * day_index + rng.gauss(0, 6))
    dia = round(b.dia + b.sys_trend * day_index / 2 + rng.gauss(0, 4))
    hr = round(b.hr + rng.gauss(0, 5))
    temp = round(b.temp + b.temp_trend * day_index + rng.gauss(0, 0.2), 1)
    spo2 = min(100, round(b.spo2 + b.spo2_trend * day_index + rng.gauss(0, 0.8)))
    truth: dict[VitalKind, float] = {"systolic_bp": sys, "diastolic_bp": dia, "heart_rate": hr}
    bp = rng.choices(
        (
            f"blood pressure {sys} over {dia}",
            f"BP's {sys} on {dia}",
            f"pressure is {sys} over {dia}",
        ),
        (0.86, 0.09, 0.05),
    )[0]
    parts = [f"{title} {p.given_name} {p.family_name}", bp]
    if correction or rng.random() < 0.06:
        parts.append(f"pulse {hr + rng.choice((-8, -6, 6, 10))}, sorry, I mean {hr}")
    else:
        parts.append(f"pulse {hr}")
    if rng.random() < 0.8:
        parts.append(f"temperature {temp}")
        truth["temperature"] = temp
    if rng.random() < 0.7:
        parts.append(f"{'oxygen' if rng.random() < 0.12 else 'sats'} {spo2} percent")
        truth["spo2"] = spo2
    if rng.random() < 0.4:
        rr = round(b.rr + rng.gauss(0, 1.5))
        parts.append(f"respiratory rate {rr}")
        truth["respiratory_rate"] = rr
    if rng.random() < 0.25:
        parts.append(rng.choice(SYMPTOM_PHRASES))
    if rng.random() < 0.2:
        parts.append(rng.choice(MED_PHRASES))
    return ", ".join(parts) + ".", truth


def reset_notes(session: Session) -> None:
    """Remove all notes, drafts and observations. The audit log is append-only and is kept."""
    session.execute(delete(ConfirmedObservation))
    session.execute(delete(Extraction))
    session.execute(delete(VoiceNote))


def seed_history(
    session: Session, now: datetime | None = None, seed: int = 7, days: int = HISTORY_DAYS
) -> int:
    """Generate the history; returns the number of notes created. Caller commits."""
    now = now or datetime.now(UTC)
    rng = random.Random(seed)  # noqa: S311 - synthetic data, not security
    llm = RuleBasedLLM()
    users = {u.username: u for u in session.scalars(select(User))}
    patients = list(session.scalars(select(Patient).order_by(Patient.ward, Patient.room)))
    baselines = {p.id: _baseline(rng, deteriorating=rng.random() < 0.2) for p in patients}
    today = now.date()
    planned: list[tuple[Patient, User, int, datetime]] = []

    for day_index in range(days + 1):
        day = today - timedelta(days=days - day_index)
        for start, chance in ROUNDS:
            round_at = datetime.combine(day, start, tzinfo=UTC)
            for ward in AUTHORS:
                at = round_at + timedelta(minutes=rng.randint(0, 20))
                for p in (p for p in patients if p.ward == ward):
                    at += timedelta(minutes=rng.randint(3, 9), seconds=rng.randint(0, 59))
                    if rng.random() > chance or at > now - timedelta(minutes=5):
                        continue
                    names, weights = zip(*AUTHORS[ward], strict=True)
                    author = users[rng.choices(names, weights)[0]]
                    planned.append((p, author, day_index, at))

    # The latest few notes of today, per ward, are still waiting for the nurse's review.
    open_drafts: set[int] = set()
    for ward, n in OPEN_DRAFTS_PER_WARD.items():
        todays = [
            i for i, (p, _, _, at) in enumerate(planned) if p.ward == ward and at.date() == today
        ]
        open_drafts.update(sorted(todays, key=lambda i: planned[i][3])[-n:])

    # One open draft on ward 3A has a spoken correction, so the review screen shows its hint.
    corrected = max((i for i in open_drafts if planned[i][0].ward == "3A"), default=None)
    for i, (p, author, day_index, at) in enumerate(planned):
        text, truth = _dictation(rng, p, baselines[p.id], day_index, correction=i == corrected)
        _add_note(session, p, author, text, truth, at, i in open_drafts, rng, llm, patients)
    count = len(planned)
    session.flush()
    return count


def _add_note(
    session: Session,
    patient: Patient,
    author: User,
    text: str,
    truth: dict[VitalKind, float],
    at: datetime,
    open_draft: bool,
    rng: random.Random,
    llm: RuleBasedLLM,
    patients: list[Patient],
) -> None:
    ward_patients = [p for p in patients if p.ward == patient.ward]
    result = run_text_pipeline(text, ward_patients=ward_patients, known_patients=patients, llm=llm)
    note = VoiceNote(
        ward=patient.ward,
        patient_id=patient.id,
        author_id=author.id,
        source="audio" if rng.random() < 0.75 else "text",
        status=NoteStatus.IN_REVIEW,
        transcript=text,
        redacted_transcript=result.redaction.text,
        redaction_map=result.redaction.mapping,
        match_status=result.match.status,
        patient_candidates=[
            {"patient_id": str(c.patient_id), "score": c.score, "matched_text": c.matched_text}
            for c in result.match.candidates[:5]
        ],
        timings_ms=result.timings_ms,
        created_at=at,
    )
    note.extractions.append(
        Extraction(
            version=1,
            payload=result.extraction.model_dump(mode="json"),
            source="ai",
            model=result.usage.model,
            prompt_version=result.prompt_version,
            input_tokens=result.usage.input_tokens,
            output_tokens=result.usage.output_tokens,
            cost_usd=result.usage.cost_usd,
            latency_ms=result.usage.latency_ms,
            created_at=at + timedelta(seconds=2),
        )
    )
    session.add(note)
    session.flush()
    if open_draft:
        return

    reviewed_at = at + timedelta(minutes=rng.randint(1, 6), seconds=rng.randint(0, 59))
    if rng.random() < 0.03:
        service.reject(session, author, note, "Dictated for the wrong patient", at=reviewed_at)
        return

    ai_payload = result.extraction
    if {v.kind: v.value for v in ai_payload.vitals} != truth:
        _nurse_edit(session, note, author, ai_payload, truth, reviewed_at - timedelta(seconds=40))
    service.confirm(session, author, note, None, at=reviewed_at)


def _nurse_edit(
    session: Session,
    note: VoiceNote,
    author: User,
    ai: ExtractionPayload,
    truth: dict[VitalKind, float],
    at: datetime,
) -> None:
    """The nurse fixes what the extractor got wrong, as a version-2 draft (audited)."""
    spans = {v.kind: v.source_text for v in ai.vitals}
    vitals = [
        Vital(
            kind=kind,
            value=value,
            unit=VITALS[kind].ucum,
            source_text=spans.get(kind, ""),
        )
        for kind, value in truth.items()
    ]
    service.edit_draft(session, author, note, ai.model_copy(update={"vitals": vitals}), None, at=at)
