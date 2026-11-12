import datetime as dt
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import Date, cast, func, select

from carenote.auth.deps import DbSession, current_user, require_roles
from carenote.auth.models import Role, User
from carenote.db import utcnow
from carenote.notes.access import note_scope
from carenote.notes.models import Extraction, VoiceNote

router = APIRouter(prefix="/metrics", tags=["metrics"], dependencies=[Depends(current_user)])


class DailyLlmMetrics(BaseModel):
    day: dt.date
    model: str
    extractions: int
    input_tokens: int
    output_tokens: int
    cost_usd: float
    avg_latency_ms: float
    max_latency_ms: int


class TranscriptionMetrics(BaseModel):
    notes: int  # audio notes transcribed in the period
    seconds: float
    cost_usd: float


class LlmMetricsOut(BaseModel):
    days: int
    ward: str | None
    total_extractions: int
    extraction_cost_usd: float
    transcription: TranscriptionMetrics
    # Extraction plus transcription: what the period actually cost.
    total_cost_usd: float
    avg_cost_per_note_usd: float
    daily: list[DailyLlmMetrics]


@router.get("/llm")
def llm_metrics(
    session: DbSession,
    user: Annotated[User, Depends(require_roles(Role.CHARGE_NURSE, Role.AUDITOR))],
    days: Annotated[int, Query(ge=1, le=365)] = 30,
) -> LlmMetricsOut:
    """Tokens, cost and latency of AI extractions per day and model, plus transcription cost.
    Charge nurses see their ward; auditors see every ward."""
    since = utcnow() - dt.timedelta(days=days)
    day = cast(Extraction.created_at, Date)
    query = (
        select(
            day.label("day"),
            Extraction.model,
            func.count(),
            func.coalesce(func.sum(Extraction.input_tokens), 0),
            func.coalesce(func.sum(Extraction.output_tokens), 0),
            func.coalesce(func.sum(Extraction.cost_usd), 0.0),
            func.coalesce(func.avg(Extraction.latency_ms), 0.0),
            func.coalesce(func.max(Extraction.latency_ms), 0),
        )
        .join(VoiceNote, VoiceNote.id == Extraction.note_id)
        .where(Extraction.source == "ai", Extraction.created_at >= since)
        .group_by(day, Extraction.model)
        .order_by(day, Extraction.model)
    )
    query = query.where(note_scope(user))
    daily = [
        DailyLlmMetrics(
            day=row[0],
            model=row[1] or "unknown",
            extractions=row[2],
            input_tokens=int(row[3]),
            output_tokens=int(row[4]),
            cost_usd=round(float(row[5]), 6),
            avg_latency_ms=round(float(row[6]), 1),
            max_latency_ms=int(row[7]),
        )
        for row in session.execute(query)
    ]
    total = sum(d.extractions for d in daily)
    extraction_cost = sum(d.cost_usd for d in daily)
    transcribed = session.execute(
        select(
            func.count(),
            func.coalesce(func.sum(VoiceNote.audio_duration_s), 0.0),
            func.coalesce(func.sum(VoiceNote.transcription_cost_usd), 0.0),
        ).where(
            note_scope(user),
            VoiceNote.transcription_model.is_not(None),
            VoiceNote.created_at >= since,
        )
    ).one()
    transcription = TranscriptionMetrics(
        notes=int(transcribed[0]),
        seconds=round(float(transcribed[1] or 0.0), 1),
        cost_usd=round(float(transcribed[2] or 0.0), 6),
    )
    cost = extraction_cost + transcription.cost_usd
    return LlmMetricsOut(
        days=days,
        ward=user.ward if user.role is Role.CHARGE_NURSE else None,
        total_extractions=total,
        extraction_cost_usd=round(extraction_cost, 6),
        transcription=transcription,
        total_cost_usd=round(cost, 6),
        avg_cost_per_note_usd=round(cost / total, 6) if total else 0.0,
        daily=daily,
    )
