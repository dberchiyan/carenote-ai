import datetime as dt
import uuid
from collections.abc import Sized
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from carenote.alerts.rules import Flag
from carenote.contracts.extraction import Extraction
from carenote.notes.models import NoteStatus
from carenote.pipeline.review_hints import ReviewHint


class TextNoteIn(BaseModel):
    text: str = Field(min_length=3, max_length=4000)
    patient_id: uuid.UUID | None = None


class CandidateOut(BaseModel):
    patient_id: uuid.UUID
    given_name: str
    family_name: str
    room: str
    score: float


class DraftOut(BaseModel):
    version: int
    source: Literal["ai", "nurse"]
    payload: Extraction
    flags: dict[str, Flag]
    hints: list[ReviewHint]
    model: str | None
    prompt_version: str | None
    input_tokens: int
    output_tokens: int
    cost_usd: float
    latency_ms: int
    created_at: dt.datetime


class NoteOut(BaseModel):
    id: uuid.UUID
    ward: str
    status: NoteStatus
    source: Literal["audio", "text"]
    author_id: uuid.UUID
    patient_id: uuid.UUID | None
    match_status: Literal["matched", "ambiguous", "none"] | None
    candidates: list[CandidateOut]
    transcript: str | None
    # Who produced the transcript: the provider's model, "browser" (on-device live transcript
    # sent with the upload) or "fake-transcriber" (keyless demo: a sample sentence).
    transcription_model: str | None
    draft: DraftOut | None
    error_step: str | None
    error_message: str | None
    # Processing started long ago and never finished (worker died). Retry is allowed.
    stalled: bool
    timings_ms: dict[str, int]
    created_at: dt.datetime
    confirmed_at: dt.datetime | None
    confirmed_by: uuid.UUID | None


class NoteSummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: NoteStatus
    patient_id: uuid.UUID | None
    author_id: uuid.UUID
    created_at: dt.datetime
    error_step: str | None


MAX_ITEMS = 50
MAX_TEXT = 2000


class DraftUpdateIn(BaseModel):
    """A nurse's edit. Stored as a new draft version; nothing is confirmed yet.

    `Extraction` itself carries no size limits because it doubles as the LLM output schema
    (structured-output APIs reject length constraints); the limits live here, at the API edge.
    """

    payload: Extraction
    patient_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def _bounded(self) -> "DraftUpdateIn":
        e = self.payload
        lists: dict[str, Sized] = {
            "vitals": e.vitals,
            "symptoms": e.symptoms,
            "medications": e.medications,
            "uncertain": e.uncertain,
        }
        for name, items in lists.items():
            if len(items) > MAX_ITEMS:
                raise ValueError(f"{name}: at most {MAX_ITEMS} entries")
        texts = [
            e.patient_mention or "",
            e.free_text_summary,
            *e.symptoms,
            *e.uncertain,
            *(v.source_text for v in e.vitals),
            *(f"{m.name}{m.dose or ''}{m.route or ''}{m.source_text}" for m in e.medications),
        ]
        if any(len(t) > MAX_TEXT for t in texts):
            raise ValueError(f"text fields: at most {MAX_TEXT} characters each")
        return self


class ConfirmIn(BaseModel):
    patient_id: uuid.UUID | None = None


class RejectIn(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


class TranscriptOut(BaseModel):
    """A transcript preview of a recording that has not been sent as a note."""

    text: str
    model: str
    latency_ms: int
