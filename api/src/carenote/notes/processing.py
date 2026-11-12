"""Background processing of a note through the pipeline, persisting each step.

Failures leave the note in its last good status with `error_step` / `error_message` set, so the
nurse sees what went wrong and can retry.
"""

import logging
import time
import uuid
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from carenote.contracts.llm import LLMProvider, ProviderError, TranscriptionProvider
from carenote.db import utcnow
from carenote.notes.models import Extraction, NoteStatus, VoiceNote
from carenote.observability import bound_note
from carenote.patients.models import Patient
from carenote.pipeline.core import PipelineError, run_text_pipeline

log = logging.getLogger(__name__)

SessionFactory = Callable[[], Session]


def _fail(session: Session, note: VoiceNote, step: str, message: str) -> None:
    note.error_step = step
    note.error_message = message
    session.commit()
    log.warning("note failed at %s: %s", step, message, extra={"step": step, "outcome": "failed"})


def _transcribe(
    session: Session, note: VoiceNote, transcription: TranscriptionProvider, audio_dir: Path
) -> bool:
    if note.audio_path is None:
        _fail(session, note, "transcribe", "No audio stored for this note.")
        return False
    path = audio_dir / Path(note.audio_path).name
    try:
        result = transcription.transcribe(
            path.read_bytes(), path.name, note.audio_mime or "audio/webm", note.audio_duration_s
        )
    except (ProviderError, OSError) as exc:
        _fail(session, note, "transcribe", f"Transcription failed: {exc}")
        return False
    if not result.text.strip():
        _fail(session, note, "transcribe", "No speech was recognised. Please record again.")
        return False
    note.transcript = result.text.strip()
    note.status = NoteStatus.TRANSCRIBED
    note.transcription_model = result.model
    note.transcription_cost_usd = result.cost_usd
    note.timings_ms = {**(note.timings_ms or {}), "transcribe": result.latency_ms}
    session.commit()
    log.info(
        "transcribed with %s in %d ms",
        result.model,
        result.latency_ms,
        extra={
            "step": "transcribe",
            "model": result.model,
            "latency_ms": result.latency_ms,
            "cost_usd": result.cost_usd,
            "chars": len(note.transcript),
        },
    )
    return True


def _extract(session: Session, note: VoiceNote, llm: LLMProvider) -> None:
    all_patients = list(session.scalars(select(Patient)).all())
    ward_patients = [p for p in all_patients if p.ward == note.ward]
    try:
        result = run_text_pipeline(
            note.transcript or "",
            ward_patients=list(ward_patients),
            known_patients=list(all_patients),
            llm=llm,
        )
    except PipelineError as exc:
        _fail(session, note, exc.step, f"{exc.step.capitalize()} step failed: {exc}")
        return

    note.redacted_transcript = result.redaction.text
    note.redaction_map = result.redaction.mapping
    note.match_status = result.match.status
    note.patient_candidates = [
        {"patient_id": str(c.patient_id), "score": c.score, "matched_text": c.matched_text}
        for c in result.match.candidates[:5]
    ]
    if note.patient_id is None and result.match.selected_id is not None:
        note.patient_id = result.match.selected_id
    note.timings_ms = {**(note.timings_ms or {}), **result.timings_ms}
    note.extractions.append(
        Extraction(
            version=len(note.extractions) + 1,
            payload=result.extraction.model_dump(mode="json"),
            source="ai",
            model=result.usage.model,
            prompt_version=result.prompt_version,
            input_tokens=result.usage.input_tokens,
            output_tokens=result.usage.output_tokens,
            cost_usd=result.usage.cost_usd,
            latency_ms=result.usage.latency_ms,
        )
    )
    note.status = NoteStatus.IN_REVIEW  # the draft is ready for the nurse
    session.commit()
    log.info(
        "draft ready: %s, %d vitals",
        result.usage.model,
        len(result.extraction.vitals),
        extra={
            "step": "extract",
            "model": result.usage.model,
            "input_tokens": result.usage.input_tokens,
            "output_tokens": result.usage.output_tokens,
            "cost_usd": result.usage.cost_usd,
            "latency_ms": result.usage.latency_ms,
            "match": result.match.status,
            "outcome": "in_review",
        },
    )


def is_stalled(note: VoiceNote, timeout_s: int, now: datetime | None = None) -> bool:
    """Still in a processing status, no recorded failure, and older than the timeout: the worker
    died mid-way (process restart, crash). Such a note may be retried from its last good step."""
    if note.status not in (NoteStatus.UPLOADED, NoteStatus.TRANSCRIBED) or note.error_step:
        return False
    return ((now or utcnow()) - note.created_at).total_seconds() > timeout_s


def process_note(
    note_id: uuid.UUID,
    *,
    session_factory: SessionFactory,
    llm: LLMProvider,
    transcription: TranscriptionProvider,
    audio_dir: Path,
    deadline_s: float | None = None,
    clock: Callable[[], float] = time.monotonic,
) -> None:
    """Run the remaining steps for a note. Any failure, expected or not, is recorded on the note
    so it never sits in a processing status with no explanation and no way to retry. Past
    `deadline_s` the note fails before the next step rather than holding the worker."""
    started = clock()

    def over_budget() -> bool:
        return deadline_s is not None and clock() - started > deadline_s

    with bound_note(note_id), session_factory() as session:
        note = session.get(VoiceNote, note_id)
        if note is None:
            log.error("note vanished before processing")
            return
        note.error_step = note.error_message = None
        step = "transcribe" if note.status is NoteStatus.UPLOADED else "extract"
        try:
            if note.status is NoteStatus.UPLOADED and not _transcribe(
                session, note, transcription, audio_dir
            ):
                return
            if note.status is NoteStatus.TRANSCRIBED:
                step = "extract"
                if over_budget():
                    _fail(session, note, step, f"Processing took longer than {deadline_s:.0f} s.")
                    return
                _extract(session, note, llm)
        except Exception as exc:
            log.exception("unexpected error at %s", step, extra={"step": step})
            session.rollback()
            _fail(session, note, step, f"Unexpected error during {step}: {type(exc).__name__}")
