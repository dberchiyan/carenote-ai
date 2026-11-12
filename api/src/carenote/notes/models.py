"""Voice notes, AI/nurse draft versions and confirmed observations."""

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from carenote.alerts.rules import FLAGS
from carenote.clinical.vitals import VITALS
from carenote.db import Base, UuidPk, utcnow


class NoteStatus(enum.StrEnum):
    UPLOADED = "uploaded"
    TRANSCRIBED = "transcribed"
    IN_REVIEW = "in_review"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"


def _enum(e: type[enum.StrEnum], name: str) -> Enum:
    return Enum(e, name=name, values_callable=lambda members: [m.value for m in members])


def _one_of(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


class VoiceNote(UuidPk, Base):
    __tablename__ = "voice_notes"
    __table_args__ = (
        CheckConstraint(_one_of("source", ("audio", "text")), name="ck_voice_notes_source"),
        Index("ix_voice_notes_author_created", "author_id", "created_at"),
    )

    ward: Mapped[str] = mapped_column(String(32), index=True)
    patient_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("patients.id"), index=True)
    author_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    source: Mapped[str] = mapped_column(String(16))  # "audio" | "text"
    audio_path: Mapped[str | None] = mapped_column(String(512))
    audio_mime: Mapped[str | None] = mapped_column(String(64))
    audio_duration_s: Mapped[float | None] = mapped_column(Float)
    transcription_model: Mapped[str | None] = mapped_column(String(64))
    transcription_cost_usd: Mapped[float] = mapped_column(Float, default=0.0, server_default="0")
    status: Mapped[NoteStatus] = mapped_column(_enum(NoteStatus, "note_status"), index=True)
    transcript: Mapped[str | None] = mapped_column(Text)
    redacted_transcript: Mapped[str | None] = mapped_column(Text)
    # Placeholder -> original text. Server-side only; never sent to providers or the browser.
    redaction_map: Mapped[dict[str, Any] | None]
    patient_candidates: Mapped[list[Any] | None]
    match_status: Mapped[str | None] = mapped_column(String(16))
    timings_ms: Mapped[dict[str, Any] | None]
    error_step: Mapped[str | None] = mapped_column(String(16))
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=utcnow, index=True)
    confirmed_at: Mapped[datetime | None]
    confirmed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))

    extractions: Mapped[list["Extraction"]] = relationship(
        back_populates="note", order_by="Extraction.version", cascade="all, delete-orphan"
    )

    @property
    def latest_extraction(self) -> "Extraction | None":
        return self.extractions[-1] if self.extractions else None


class Extraction(UuidPk, Base):
    """One draft version. Version 1 comes from the LLM; later versions are nurse edits."""

    __tablename__ = "extractions"
    __table_args__ = (
        UniqueConstraint("note_id", "version"),
        CheckConstraint(_one_of("source", ("ai", "nurse")), name="ck_extractions_source"),
    )

    note_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("voice_notes.id"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    payload: Mapped[dict[str, Any]]
    source: Mapped[str] = mapped_column(String(16))  # "ai" | "nurse"
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    model: Mapped[str | None] = mapped_column(String(64))
    prompt_version: Mapped[str | None] = mapped_column(String(32))
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    note: Mapped[VoiceNote] = relationship(back_populates="extractions")


class ConfirmedObservation(UuidPk, Base):
    """Written only when a nurse confirms a draft. Never by the AI."""

    __tablename__ = "confirmed_observations"
    __table_args__ = (
        CheckConstraint(_one_of("flag", FLAGS), name="ck_confirmed_observations_flag"),
        CheckConstraint(_one_of("kind", tuple(VITALS)), name="ck_confirmed_observations_kind"),
        Index(
            "ix_confirmed_observations_patient_kind_effective",
            "patient_id",
            "kind",
            "effective_at",
        ),
    )

    note_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("voice_notes.id"), index=True)
    patient_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("patients.id"), index=True)
    kind: Mapped[str] = mapped_column(String(32))
    code: Mapped[str] = mapped_column(String(16))  # LOINC
    value: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(16))  # UCUM
    effective_at: Mapped[datetime] = mapped_column(index=True)
    flag: Mapped[str] = mapped_column(String(16))
    # Which alert rules produced `flag`: the stored flag stays authoritative when rules change.
    rules_version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
