"""HTTP layer for notes: parse the request, call the service, commit, present. No rules here."""

import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Query, UploadFile, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from carenote.auth.deps import CurrentUser, DbSession, current_user, require_roles
from carenote.auth.models import Role, User
from carenote.config import Settings, get_settings
from carenote.contracts.llm import LLMProvider, TranscriptionProvider
from carenote.db import get_session_factory
from carenote.errors import conflict
from carenote.notes import service
from carenote.notes.access import get_note_for, note_scope
from carenote.notes.models import VoiceNote
from carenote.notes.presenters import note_out
from carenote.notes.processing import process_note
from carenote.notes.schemas import (
    ConfirmIn,
    DraftUpdateIn,
    NoteOut,
    NoteSummaryOut,
    RejectIn,
    TextNoteIn,
    TranscriptOut,
)
from carenote.providers.factory import get_llm, get_transcription

router = APIRouter(prefix="/notes", tags=["notes"], dependencies=[Depends(current_user)])

Author = Annotated[User, Depends(require_roles(Role.NURSE, Role.CHARGE_NURSE))]
SessionFactory = Annotated[sessionmaker[Session], Depends(get_session_factory)]
Llm = Annotated[LLMProvider, Depends(get_llm)]
Transcriber = Annotated[TranscriptionProvider, Depends(get_transcription)]
AppSettings = Annotated[Settings, Depends(get_settings)]


def _schedule(
    tasks: BackgroundTasks,
    note_id: uuid.UUID,
    factory: sessionmaker[Session],
    llm: LLMProvider,
    transcription: TranscriptionProvider,
    settings: Settings,
) -> None:
    tasks.add_task(
        process_note,
        note_id,
        session_factory=factory,
        llm=llm,
        transcription=transcription,
        audio_dir=settings.audio_dir,
        deadline_s=settings.pipeline_deadline_s,
    )


@router.post("", status_code=status.HTTP_202_ACCEPTED)
def upload_note(
    session: DbSession,
    user: Author,
    tasks: BackgroundTasks,
    factory: SessionFactory,
    llm: Llm,
    transcription: Transcriber,
    settings: AppSettings,
    audio: Annotated[UploadFile, File(description="WebM, WAV, MP3 or M4A; max 2 minutes")],
    patient_id: Annotated[uuid.UUID | None, Form()] = None,
    transcript: Annotated[
        str | None,
        Form(
            max_length=4000,
            description="On-device live transcript reviewed by the nurse; skips transcription.",
        ),
    ] = None,
) -> NoteOut:
    """Upload a voice note. Transcription and extraction run in the background."""
    data = audio.file.read(settings.max_upload_bytes + 1)
    note = service.create_audio_note(
        session, user, data, audio.content_type, patient_id, settings, transcript=transcript
    )
    session.commit()
    _schedule(tasks, note.id, factory, llm, transcription, settings)
    return note_out(session, note)


@router.post("/transcribe")
def transcribe_preview(
    user: Author,
    transcription: Transcriber,
    settings: AppSettings,
    audio: Annotated[UploadFile, File(description="The recording, before it is sent as a note")],
) -> TranscriptOut:
    """Transcribe a recording so the nurse can read and correct the text before sending it.
    Nothing is stored and no note is created."""
    data = audio.file.read(settings.max_upload_bytes + 1)
    result = service.transcribe_preview(data, audio.content_type, settings, transcription)
    return TranscriptOut(text=result.text, model=result.model, latency_ms=result.latency_ms)


@router.post("/text", status_code=status.HTTP_202_ACCEPTED)
def create_text_note(
    body: TextNoteIn,
    session: DbSession,
    user: Author,
    tasks: BackgroundTasks,
    factory: SessionFactory,
    llm: Llm,
    transcription: Transcriber,
    settings: AppSettings,
) -> NoteOut:
    """Create a note from typed text (skips transcription). Useful without a microphone."""
    note = service.create_text_note(session, user, body.text, body.patient_id)
    session.commit()
    _schedule(tasks, note.id, factory, llm, transcription, settings)
    return note_out(session, note)


@router.get("")
def list_notes(
    session: DbSession, user: CurrentUser, limit: Annotated[int, Query(ge=1, le=200)] = 50
) -> list[NoteSummaryOut]:
    """Recent notes visible to the caller."""
    query = select(VoiceNote).where(note_scope(user)).order_by(VoiceNote.created_at.desc())
    return [NoteSummaryOut.model_validate(n) for n in session.scalars(query.limit(limit))]


@router.get("/{note_id}")
def get_note(note_id: uuid.UUID, session: DbSession, user: CurrentUser) -> NoteOut:
    return note_out(session, get_note_for(session, user, note_id, write=False))


@router.post("/{note_id}/retry", status_code=status.HTTP_202_ACCEPTED)
def retry_note(
    note_id: uuid.UUID,
    session: DbSession,
    user: Author,
    tasks: BackgroundTasks,
    factory: SessionFactory,
    llm: Llm,
    transcription: Transcriber,
    settings: AppSettings,
) -> NoteOut:
    """Re-run the pipeline from the last good step after a failure."""
    note = get_note_for(session, user, note_id, write=True)
    service.request_retry(session, user, note, settings.processing_timeout_s)
    session.commit()
    _schedule(tasks, note.id, factory, llm, transcription, settings)
    return note_out(session, note)


@router.patch("/{note_id}/draft")
def update_draft(
    note_id: uuid.UUID, body: DraftUpdateIn, session: DbSession, user: Author
) -> NoteOut:
    """Save the nurse's corrections as a new draft version (audited)."""
    note = get_note_for(session, user, note_id, write=True)
    draft = service.edit_draft(session, user, note, body.payload, body.patient_id)
    try:
        session.commit()
    except IntegrityError as exc:  # (note_id, version) unique: someone saved in between
        session.rollback()
        raise conflict(
            "The draft changed while you were editing. Reload it.", version=draft.version - 1
        ) from exc
    return note_out(session, note)


@router.post("/{note_id}/confirm")
def confirm_note(note_id: uuid.UUID, body: ConfirmIn, session: DbSession, user: Author) -> NoteOut:
    """The nurse confirms the draft: only now are observations written."""
    note = get_note_for(session, user, note_id, write=True)
    service.confirm(session, user, note, body.patient_id)
    session.commit()
    return note_out(session, note)


@router.post("/{note_id}/reject")
def reject_note(note_id: uuid.UUID, body: RejectIn, session: DbSession, user: Author) -> NoteOut:
    note = get_note_for(session, user, note_id, write=True)
    service.reject(session, user, note, body.reason)
    session.commit()
    return note_out(session, note)
