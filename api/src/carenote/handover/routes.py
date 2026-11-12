"""Shift handover for the caller's ward: confirmed data, ordered by who needs attention."""

import datetime as dt
from functools import cache
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from carenote.audit import service as audit
from carenote.auth.deps import DbSession, current_user, require_roles
from carenote.auth.models import Role, User
from carenote.config import get_settings
from carenote.contracts.handover import HandoverWriter
from carenote.db import utcnow
from carenote.errors import forbidden
from carenote.handover.schemas import HandoverOut, HandoverPatientOut
from carenote.handover.service import build_handover
from carenote.handover.writer import RuleBasedHandoverWriter

router = APIRouter(prefix="/handover", tags=["handover"], dependencies=[Depends(current_user)])
Clinician = Annotated[User, Depends(require_roles(Role.NURSE, Role.CHARGE_NURSE))]


@cache
def get_handover_writer() -> HandoverWriter:
    """Claude when an Anthropic key is configured for extraction, else the rule-based writer."""
    settings = get_settings()
    if settings.llm_provider == "anthropic" and settings.anthropic_api_key is not None:
        from carenote.pipeline.prompts import load_prompt
        from carenote.providers.anthropic_handover import AnthropicHandoverWriter

        return AnthropicHandoverWriter(
            settings.anthropic_api_key.get_secret_value(),
            load_prompt("handover_v1"),
            timeout_s=settings.provider_timeout_s,
        )
    return RuleBasedHandoverWriter()


Writer = Annotated[HandoverWriter, Depends(get_handover_writer)]


@router.get("")
def shift_handover(
    session: DbSession,
    user: Clinician,
    writer: Writer,
    hours: Annotated[int, Query(ge=4, le=48)] = 12,
) -> HandoverOut:
    """The last `hours` on the caller's ward: flagged patients first, then drafts to review,
    then stable ones. Built from confirmed observations only. Audited."""
    if user.ward is None:
        raise forbidden("No ward assigned")
    now = utcnow()
    facts, patients = build_handover(session, user.ward, hours, now)
    text, written_by = writer.write(facts)
    by_room = {r.room: r.summary for r in text.patients}
    audit.record(
        session,
        actor_id=user.id,
        action="handover.view",
        entity="ward",
        entity_id=user.ward,
        after={"hours": hours, "patients": len(patients), "written_by": written_by},
    )
    session.commit()
    return HandoverOut(
        ward=user.ward,
        hours=hours,
        since=now - dt.timedelta(hours=hours),
        until=now,
        summary=text.ward_summary,
        written_by=written_by,
        counts={
            k: sum(1 for f in facts.patients if f.priority == k)
            for k in ("critical", "warning", "review", "stable")
        },
        unassigned_drafts=facts.unassigned_drafts,
        patients=[
            HandoverPatientOut(
                patient_id=p.id,
                given_name=p.given_name,
                family_name=p.family_name,
                room=p.room,
                priority=f.priority,
                summary=by_room.get(f.room, ""),
                vitals=f.vitals,
                symptoms=f.symptoms,
                medications=f.medications,
                notes_confirmed=f.notes_confirmed,
                open_drafts=f.open_drafts,
            )
            for f, p in zip(facts.patients, patients, strict=True)
        ],
    )
