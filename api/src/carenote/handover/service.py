"""Build a ward's shift handover from confirmed data only.

For each patient: the latest confirmed value of every vital in the shift, compared with the last
value before it; the worst flag seen during the shift (a transient critical is never hidden by a
later normal reading); symptoms and medications from notes confirmed in the shift; open drafts.
Patients are ordered by priority: critical, warning, waiting for review, stable.
"""

import datetime as dt
import uuid
from collections import defaultdict
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.orm import Session, selectinload

from carenote.clinical.vitals import VITALS
from carenote.contracts.handover import (
    Change,
    HandoverFacts,
    MedicationFact,
    PatientFacts,
    Priority,
    VitalFact,
)
from carenote.db import utcnow
from carenote.notes.models import ConfirmedObservation, NoteStatus, VoiceNote
from carenote.patients.models import Patient

RANK = {"normal": 0, "warning": 1, "critical": 2}
# Handover vocabulary: the short labels nurses say aloud and the ward board shows.
SHORT_LABEL = {
    "spo2": "SpO₂", "respiratory_rate": "RR", "heart_rate": "HR", "temperature": "Temp",
    "systolic_bp": "SBP", "diastolic_bp": "DBP", "blood_glucose": "Glucose", "weight": "Weight",
}  # fmt: skip
PRIORITY_ORDER: dict[Priority, int] = {"critical": 0, "warning": 1, "review": 2, "stable": 3}
# Vital order on the page and in the text: the ones that decide escalation first.
KIND_ORDER = [
    "spo2", "respiratory_rate", "systolic_bp", "diastolic_bp", "heart_rate", "temperature",
    "blood_glucose", "weight",
]  # fmt: skip


def _flag(value: str) -> Any:
    return value if value in RANK else "normal"


def _change(flag: str, previous_flag: str | None, value: float, previous: float | None) -> Change:
    if previous is None or previous_flag is None:
        return "first"
    if RANK[flag] > RANK[previous_flag]:
        return "new_flag" if RANK[previous_flag] == 0 else "worse"
    if RANK[flag] < RANK[previous_flag]:
        return "better"
    return "same"


def build_handover(
    session: Session, ward: str, hours: int, now: dt.datetime | None = None
) -> tuple[HandoverFacts, list[Patient]]:
    """The facts (rooms only, for a writer) and the patients in the same order (for the page)."""
    now = now or utcnow()
    since = now - dt.timedelta(hours=hours)
    patients = list(session.scalars(select(Patient).where(Patient.ward == ward)))
    ids = [p.id for p in patients]

    current: dict[uuid.UUID, dict[str, list[ConfirmedObservation]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for o in session.scalars(
        select(ConfirmedObservation)
        .where(
            ConfirmedObservation.patient_id.in_(ids),
            ConfirmedObservation.effective_at >= since,
            ConfirmedObservation.effective_at <= now,
        )
        .order_by(ConfirmedObservation.effective_at)
    ):
        current[o.patient_id][o.kind].append(o)

    before: dict[tuple[uuid.UUID, str], ConfirmedObservation] = {
        (o.patient_id, o.kind): o
        for o in session.scalars(
            select(ConfirmedObservation)
            .ext(distinct_on(ConfirmedObservation.patient_id, ConfirmedObservation.kind))
            .where(
                ConfirmedObservation.patient_id.in_(ids),
                ConfirmedObservation.effective_at < since,
            )
            .order_by(
                ConfirmedObservation.patient_id,
                ConfirmedObservation.kind,
                ConfirmedObservation.effective_at.desc(),
            )
        )
    }

    confirmed: dict[uuid.UUID, list[VoiceNote]] = defaultdict(list)
    for note in session.scalars(
        select(VoiceNote)
        .options(selectinload(VoiceNote.extractions))
        .where(
            VoiceNote.ward == ward,
            VoiceNote.status == NoteStatus.CONFIRMED,
            VoiceNote.confirmed_at >= since,
            VoiceNote.confirmed_at <= now,
        )
        .order_by(VoiceNote.confirmed_at)
    ):
        if note.patient_id is not None:
            confirmed[note.patient_id].append(note)

    drafts: dict[uuid.UUID | None, int] = defaultdict(int)
    for pid in session.scalars(
        select(VoiceNote.patient_id).where(
            VoiceNote.ward == ward, VoiceNote.status == NoteStatus.IN_REVIEW
        )
    ):
        drafts[pid] += 1

    facts: list[tuple[PatientFacts, Patient]] = []
    for p in patients:
        vitals: list[VitalFact] = []
        for kind in sorted(
            current[p.id], key=lambda k: KIND_ORDER.index(k) if k in KIND_ORDER else 99
        ):
            readings = current[p.id][kind]
            latest = readings[-1]
            prev = before.get((p.id, kind))
            spec = VITALS[kind]  # type: ignore[index]
            vitals.append(
                VitalFact(
                    label=SHORT_LABEL.get(kind, spec.display),
                    kind=kind,
                    value=latest.value,
                    unit=spec.unit_label,
                    flag=_flag(latest.flag),
                    previous=prev.value if prev else None,
                    change=_change(
                        _flag(latest.flag),
                        _flag(prev.flag) if prev else None,
                        latest.value,
                        prev.value if prev else None,
                    ),
                    worst_in_shift=max((_flag(r.flag) for r in readings), key=RANK.__getitem__),
                )
            )
        symptoms: list[str] = []
        medications: list[MedicationFact] = []
        for note in confirmed[p.id]:
            payload = note.latest_extraction.payload if note.latest_extraction else {}
            for s in payload.get("symptoms", []):
                if s not in symptoms:
                    symptoms.append(s)
            for m in payload.get("medications", []):
                medications.append(
                    MedicationFact(name=m.get("name", ""), dose=m.get("dose"), route=m.get("route"))
                )
        worst = max((RANK[v.worst_in_shift] for v in vitals), default=0)
        priority: Priority = (
            "critical" if worst == 2 else "warning" if worst == 1 else
            "review" if drafts.get(p.id) else "stable"
        )  # fmt: skip
        facts.append(
            (
                PatientFacts(
                    room=p.room,
                    priority=priority,
                    vitals=vitals,
                    symptoms=symptoms,
                    medications=medications,
                    notes_confirmed=len(confirmed[p.id]),
                    open_drafts=drafts.get(p.id, 0),
                ),
                p,
            )
        )

    facts.sort(key=lambda pair: (PRIORITY_ORDER[pair[0].priority], pair[1].room))
    return (
        HandoverFacts(
            ward=ward,
            hours=hours,
            patients=[f for f, _ in facts],
            unassigned_drafts=drafts.get(None, 0),
        ),
        [p for _, p in facts],
    )
