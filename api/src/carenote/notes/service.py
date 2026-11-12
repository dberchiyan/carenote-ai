"""The use cases on a note: create, edit the draft, confirm, reject, retry.

Routes and the demo seeder call these; nothing else writes notes, drafts or observations.
Each function changes the session and records the audit event; the caller commits, so one
request is one transaction. `at` lets the seeder backdate an action deterministically.
"""

import tempfile
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import status
from sqlalchemy.orm import Session

from carenote.alerts.rules import default_rules
from carenote.audit import service as audit
from carenote.auth.models import User
from carenote.config import Settings
from carenote.contracts.extraction import Extraction as ExtractionPayload
from carenote.contracts.llm import ProviderError, TranscriptionProvider, TranscriptionResult
from carenote.db import utcnow
from carenote.errors import ApiError, ErrorCode, forbidden, invalid_state, payload_rejected
from carenote.notes.audio import AudioRejectedError, duration_seconds, validate_upload
from carenote.notes.confirm import observations_for
from carenote.notes.identity import deidentify
from carenote.notes.models import ConfirmedObservation, Extraction, NoteStatus, VoiceNote
from carenote.notes.processing import is_stalled
from carenote.patients.access import get_patient_for
from carenote.pipeline.validate import validate_extraction


def create_text_note(
    session: Session, user: User, text: str, patient_id: uuid.UUID | None
) -> VoiceNote:
    """A typed note skips transcription and goes straight to extraction."""
    if patient_id is not None:
        get_patient_for(session, user, patient_id)
    note = VoiceNote(
        ward=user.ward,
        author_id=user.id,
        patient_id=patient_id,
        source="text",
        status=NoteStatus.TRANSCRIBED,
        transcript=text.strip(),
    )
    session.add(note)
    session.flush()
    audit.record(
        session,
        actor_id=user.id,
        action="note.create",
        entity="note",
        entity_id=note.id,
        after={"source": "text", "chars": len(note.transcript or "")},
    )
    return note


BROWSER_TRANSCRIPTION = "browser"


def transcribe_preview(
    data: bytes, content_type: str | None, settings: Settings, transcription: TranscriptionProvider
) -> TranscriptionResult:
    """Transcribe a recording the nurse has not sent yet, so she can read and fix the text
    before a note exists. Nothing is stored; the same checks as an upload apply."""
    try:
        ext = validate_upload(data, content_type, settings.max_upload_bytes)
    except AudioRejectedError as exc:
        raise payload_rejected(str(exc)) from exc
    with tempfile.NamedTemporaryFile(suffix=f".{ext}") as tmp:
        tmp.write(data)
        tmp.flush()
        try:
            duration = duration_seconds(Path(tmp.name), data, ext)
        except AudioRejectedError as exc:
            raise payload_rejected(str(exc)) from exc
    if duration > settings.max_audio_seconds:
        raise payload_rejected(
            f"Recordings can be at most {settings.max_audio_seconds:.0f} seconds.",
            max_seconds=settings.max_audio_seconds,
        )
    try:
        return transcription.transcribe(data, f"preview.{ext}", content_type or "", duration)
    except ProviderError as exc:
        raise ApiError(
            status.HTTP_502_BAD_GATEWAY, ErrorCode.INTERNAL_ERROR, f"Transcription failed: {exc}"
        ) from exc


def create_audio_note(
    session: Session,
    user: User,
    data: bytes,
    content_type: str | None,
    patient_id: uuid.UUID | None,
    settings: Settings,
    transcript: str | None = None,
) -> VoiceNote:
    """Validate and store a recording. Nothing is kept when the audio is rejected.

    `transcript` is what the browser recognised on the device while recording, already
    reviewed by the nurse; when present it is used as is and the transcription step is skipped.
    """
    if patient_id is not None:
        get_patient_for(session, user, patient_id)
    try:
        ext = validate_upload(data, content_type, settings.max_upload_bytes)
    except AudioRejectedError as exc:
        raise payload_rejected(str(exc)) from exc

    note = VoiceNote(
        ward=user.ward,
        author_id=user.id,
        patient_id=patient_id,
        source="audio",
        status=NoteStatus.UPLOADED,
        audio_mime=content_type,
    )
    session.add(note)
    session.flush()
    settings.audio_dir.mkdir(parents=True, exist_ok=True)
    path = settings.audio_dir / f"{note.id}.{ext}"
    path.write_bytes(data)
    try:
        duration = duration_seconds(path, data, ext)
        if duration > settings.max_audio_seconds:
            raise AudioRejectedError(
                f"Recordings can be at most {settings.max_audio_seconds:.0f} seconds."
            )
    except AudioRejectedError as exc:
        path.unlink(missing_ok=True)
        session.rollback()
        raise payload_rejected(str(exc), max_seconds=settings.max_audio_seconds) from exc

    note.audio_path = path.name
    note.audio_duration_s = round(duration, 2)
    transcript = (transcript or "").strip()
    if transcript:
        note.transcript = transcript
        note.transcription_model = BROWSER_TRANSCRIPTION
        note.status = NoteStatus.TRANSCRIBED
    audit.record(
        session,
        actor_id=user.id,
        action="note.upload",
        entity="note",
        entity_id=note.id,
        after={
            "bytes": len(data),
            "type": ext,
            "seconds": note.audio_duration_s,
            "transcript": BROWSER_TRANSCRIPTION if transcript else None,
        },
    )
    return note


def request_retry(session: Session, user: User, note: VoiceNote, timeout_s: int) -> None:
    """Allowed after a recorded failure, or when the worker died mid-way (stalled)."""
    if note.error_step is None and not is_stalled(note, timeout_s):
        raise invalid_state("Note has not failed", status=note.status.value)
    audit.record(session, actor_id=user.id, action="note.retry", entity="note", entity_id=note.id)


def _draft_in_review(note: VoiceNote) -> Extraction:
    if note.status is not NoteStatus.IN_REVIEW or note.latest_extraction is None:
        raise invalid_state(f"Note is {note.status.value}, not in review", status=note.status.value)
    return note.latest_extraction


def _select_patient(session: Session, user: User, note: VoiceNote, patient_id: uuid.UUID) -> None:
    patient = get_patient_for(session, user, patient_id)
    if patient.ward != note.ward:
        raise forbidden("Patient is not on this note's ward", ward=note.ward)
    note.patient_id = patient.id


def _draft_snapshot(note: VoiceNote, version: int, payload: dict[str, Any]) -> dict[str, Any]:
    """What the audit log keeps of a draft: enough to show the exact change, names redacted."""
    return {"version": version, "patient_id": str(note.patient_id), **payload}


def edit_draft(
    session: Session,
    user: User,
    note: VoiceNote,
    payload: ExtractionPayload,
    patient_id: uuid.UUID | None,
    *,
    at: datetime | None = None,
) -> Extraction:
    """Store the nurse's corrections as a new draft version. The browser saw real names, so the
    stored version and the audit entry are de-identified back to placeholders first."""
    latest = _draft_in_review(note)
    before = _draft_snapshot(note, latest.version, latest.payload)
    if patient_id is not None:
        _select_patient(session, user, note, patient_id)
    deidentified = deidentify(payload, note.redaction_map or {})
    stored = validate_extraction(deidentified).model_dump(mode="json")
    draft = Extraction(
        version=latest.version + 1,
        payload=stored,
        source="nurse",
        created_by=user.id,
        model=latest.model,
        prompt_version=latest.prompt_version,
        created_at=at or utcnow(),
    )
    note.extractions.append(draft)
    event = audit.record(
        session,
        actor_id=user.id,
        action="note.draft_edit",
        entity="note",
        entity_id=note.id,
        before=before,
        after=_draft_snapshot(note, draft.version, stored),
    )
    if at is not None:
        event.at = at
    return draft


def confirm(
    session: Session,
    user: User,
    note: VoiceNote,
    patient_id: uuid.UUID | None,
    *,
    at: datetime | None = None,
) -> list[ConfirmedObservation]:
    """The nurse confirms the draft: the only moment observations are written."""
    latest = _draft_in_review(note)
    if patient_id is not None:
        _select_patient(session, user, note, patient_id)
    if note.patient_id is None:
        raise invalid_state("Select the patient before confirming", status=note.status.value)
    extraction = ExtractionPayload.model_validate(latest.payload)
    observations = observations_for(note, extraction, default_rules(), effective_at=note.created_at)
    session.add_all(observations)
    note.status = NoteStatus.CONFIRMED
    note.confirmed_at = at or utcnow()
    note.confirmed_by = user.id
    event = audit.record(
        session,
        actor_id=user.id,
        action="note.confirm",
        entity="note",
        entity_id=note.id,
        after={
            "patient_id": str(note.patient_id),
            "draft_version": latest.version,
            "observations": [
                {"code": o.code, "value": o.value, "unit": o.unit, "flag": o.flag}
                for o in observations
            ],
        },
    )
    if at is not None:
        event.at = at
    return observations


def reject(
    session: Session,
    user: User,
    note: VoiceNote,
    reason: str | None,
    *,
    at: datetime | None = None,
) -> None:
    if note.status in (NoteStatus.CONFIRMED, NoteStatus.REJECTED):
        raise invalid_state(f"Note is already {note.status.value}", status=note.status.value)
    note.status = NoteStatus.REJECTED
    event = audit.record(
        session,
        actor_id=user.id,
        action="note.reject",
        entity="note",
        entity_id=note.id,
        after={"reason": reason},
    )
    if at is not None:
        event.at = at
