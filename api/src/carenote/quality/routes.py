"""AI quality: offline eval reports and what nurses correct in AI drafts."""

import datetime as dt
import json
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from carenote.audit import service as audit
from carenote.auth.deps import DbSession, current_user, require_roles
from carenote.auth.models import Role, User
from carenote.config import Settings, get_settings
from carenote.contracts.extraction import Extraction
from carenote.db import utcnow
from carenote.notes.access import note_scope
from carenote.notes.models import NoteStatus, VoiceNote
from carenote.quality.corrections import FieldChange, diff_extractions, eval_case
from carenote.quality.evals import EvalRunOut, load_runs

router = APIRouter(prefix="/quality", tags=["quality"], dependencies=[Depends(current_user)])
Reviewer = Annotated[User, Depends(require_roles(Role.CHARGE_NURSE, Role.AUDITOR))]
Days = Annotated[int, Query(ge=1, le=365)]


@router.get("/evals")
def eval_runs(
    _: Reviewer, settings: Annotated[Settings, Depends(get_settings)]
) -> list[EvalRunOut]:
    """The latest offline eval run per provider, model, mode and dataset (synthetic cases)."""
    return load_runs(settings.eval_reports_dir)


class FieldStatsOut(BaseModel):
    field: str
    added: int
    removed: int
    changed: int
    total: int


class CorrectedNoteOut(BaseModel):
    note_id: str
    created_at: dt.datetime
    model: str | None
    redacted_transcript: str
    changes: list[FieldChange]


class CorrectionsOut(BaseModel):
    days: int
    ward: str | None
    confirmed_notes: int
    edited_notes: int
    edit_rate: float | None
    by_field: list[FieldStatsOut]
    recent: list[CorrectedNoteOut]


def _corrected_notes(
    session: DbSession, user: User, days: int
) -> tuple[int, list[tuple[VoiceNote, Extraction, list[FieldChange]]]]:
    """Confirmed notes in the user's scope, and those whose final version differs from the AI's."""
    query = (
        select(VoiceNote)
        .options(selectinload(VoiceNote.extractions))
        .where(
            note_scope(user),
            VoiceNote.status == NoteStatus.CONFIRMED,
            VoiceNote.created_at >= utcnow() - dt.timedelta(days=days),
        )
        .order_by(VoiceNote.created_at.desc())
    )
    notes = list(session.scalars(query))
    edited = []
    for note in notes:
        ai = next((e for e in note.extractions if e.source == "ai"), None)
        final = note.latest_extraction
        if ai is None or final is None or final.source != "nurse":
            continue
        final_extraction = Extraction.model_validate(final.payload)
        changes = diff_extractions(Extraction.model_validate(ai.payload), final_extraction)
        if changes:
            edited.append((note, final_extraction, changes))
    return len(notes), edited


@router.get("/corrections")
def corrections(session: DbSession, user: Reviewer, days: Days = 30) -> CorrectionsOut:
    """How often nurses edit AI drafts before confirming, and which fields they change.
    Charge nurses see their ward; auditors every ward. Transcripts are shown redacted."""
    confirmed, edited = _corrected_notes(session, user, days)
    stats: dict[str, dict[str, int]] = {}
    for _, _, changes in edited:
        for c in changes:
            s = stats.setdefault(c.field, {"added": 0, "removed": 0, "changed": 0})
            s[c.change] += 1
    by_field = sorted(
        (FieldStatsOut(field=f, **s, total=sum(s.values())) for f, s in stats.items()),
        key=lambda x: (-x.total, x.field),
    )
    return CorrectionsOut(
        days=days,
        ward=user.ward if user.role is Role.CHARGE_NURSE else None,
        confirmed_notes=confirmed,
        edited_notes=len(edited),
        edit_rate=round(len(edited) / confirmed, 4) if confirmed else None,
        by_field=by_field,
        recent=[
            CorrectedNoteOut(
                note_id=str(note.id),
                created_at=note.created_at,
                model=next((e.model for e in note.extractions if e.source == "ai"), None),
                redacted_transcript=note.redacted_transcript or "",
                changes=changes,
            )
            for note, _, changes in edited[:8]
        ],
    )


@router.get(
    "/corrections/export",
    response_class=Response,
    responses={200: {"content": {"application/x-ndjson": {}}}},
)
def export_corrections(session: DbSession, user: Reviewer, days: Days = 30) -> Response:
    """Nurse-corrected notes as eval cases (JSONL, redacted text). Audited.
    Save as `api/evals/data/cases_corrections.jsonl`, then `make eval DATASET=cases_corrections`."""
    _, edited = _corrected_notes(session, user, days)
    lines = [
        json.dumps(
            eval_case(
                f"correction-{note.id.hex[:8]}",
                note.ward,
                note.redacted_transcript or "",
                final,
                changes,
            ),
            sort_keys=True,
        )
        for note, final, changes in edited
    ]
    audit.record(
        session,
        actor_id=user.id,
        action="quality.corrections_export",
        entity="eval_cases",
        after={"cases": len(lines), "days": days, "ward": user.ward},
    )
    session.commit()
    return Response(
        "".join(line + "\n" for line in lines),
        media_type="application/x-ndjson",
        headers={"Content-Disposition": 'attachment; filename="cases_corrections.jsonl"'},
    )
