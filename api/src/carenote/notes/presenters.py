"""Turn stored notes into API responses (re-identifying text for authorized viewers)."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from carenote.alerts.rules import default_rules
from carenote.config import get_settings
from carenote.contracts.extraction import Extraction
from carenote.notes.identity import reidentify
from carenote.notes.models import VoiceNote
from carenote.notes.processing import is_stalled
from carenote.notes.schemas import CandidateOut, DraftOut, NoteOut
from carenote.patients.models import Patient
from carenote.pipeline.core import flag_vitals
from carenote.pipeline.review_hints import ReviewHint, review_hints


def _hints(note: VoiceNote, current: Extraction) -> list[ReviewHint]:
    """Hints come from the AI's version; a field the nurse has changed no longer needs one."""
    ai = next((e for e in note.extractions if e.source == "ai"), None)
    if ai is None:
        return []
    ai_extraction = Extraction.model_validate(ai.payload)
    now = {v.kind: v.value for v in current.vitals}
    then = {v.kind: v.value for v in ai_extraction.vitals}
    transcript = note.redacted_transcript or note.transcript or ""
    return [
        h
        for h in review_hints(ai_extraction, transcript)
        if h.kind in now and now[h.kind] == then.get(h.kind)
    ]


def note_out(session: Session, note: VoiceNote) -> NoteOut:
    candidates_raw = note.patient_candidates or []
    ids = [uuid.UUID(c["patient_id"]) for c in candidates_raw]
    patients = {p.id: p for p in session.scalars(select(Patient).where(Patient.id.in_(ids)))}
    candidates = [
        CandidateOut(
            patient_id=pid,
            given_name=patients[pid].given_name,
            family_name=patients[pid].family_name,
            room=patients[pid].room,
            score=c["score"],
        )
        for pid, c in zip(ids, candidates_raw, strict=True)
        if pid in patients
    ]

    draft = None
    latest = note.latest_extraction
    if latest is not None:
        extraction = Extraction.model_validate(latest.payload)
        draft = DraftOut(
            version=latest.version,
            source="nurse" if latest.source == "nurse" else "ai",
            payload=reidentify(extraction, note.redaction_map or {}),
            flags=flag_vitals(extraction, default_rules()),
            hints=_hints(note, extraction),
            model=latest.model,
            prompt_version=latest.prompt_version,
            input_tokens=latest.input_tokens,
            output_tokens=latest.output_tokens,
            cost_usd=latest.cost_usd,
            latency_ms=latest.latency_ms,
            created_at=latest.created_at,
        )
    return NoteOut(
        id=note.id,
        ward=note.ward,
        status=note.status,
        source="audio" if note.source == "audio" else "text",
        author_id=note.author_id,
        patient_id=note.patient_id,
        match_status=note.match_status,  # type: ignore[arg-type]
        candidates=candidates,
        transcript=note.transcript,
        transcription_model=note.transcription_model,
        draft=draft,
        error_step=note.error_step,
        error_message=note.error_message,
        stalled=is_stalled(note, get_settings().processing_timeout_s),
        timings_ms={k: int(v) for k, v in (note.timings_ms or {}).items()},
        created_at=note.created_at,
        confirmed_at=note.confirmed_at,
        confirmed_by=note.confirmed_by,
    )
