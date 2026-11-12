"""Shift handover: the facts a writer turns into text, and the writer interface.

Facts carry rooms, never names: a writer may be an LLM, and only de-identified data leaves the
process. The text comes back keyed by room and is matched to patients in our code.
"""

from typing import Literal, Protocol

from pydantic import BaseModel, Field

Priority = Literal["critical", "warning", "review", "stable"]
Change = Literal["first", "new_flag", "worse", "better", "same"]


class VitalFact(BaseModel):
    label: str  # "SpO₂", "Systolic BP"
    kind: str
    value: float
    unit: str  # display unit, "%", "mmHg"
    flag: Literal["normal", "warning", "critical"]
    previous: float | None = Field(description="Latest value before this shift, if any.")
    change: Change
    worst_in_shift: Literal["normal", "warning", "critical"]


class MedicationFact(BaseModel):
    name: str
    dose: str | None
    route: str | None


class PatientFacts(BaseModel):
    room: str
    priority: Priority
    vitals: list[VitalFact]
    symptoms: list[str]
    medications: list[MedicationFact]
    notes_confirmed: int
    open_drafts: int


class HandoverFacts(BaseModel):
    ward: str
    hours: int
    patients: list[PatientFacts]
    unassigned_drafts: int = Field(description="Drafts on the ward with no patient chosen yet.")


class RoomSummary(BaseModel):
    room: str
    summary: str


class HandoverText(BaseModel):
    """What a writer returns. Also the structured-output schema for an LLM writer."""

    ward_summary: str
    patients: list[RoomSummary]


class HandoverWriter(Protocol):
    name: str

    def write(self, facts: HandoverFacts) -> tuple[HandoverText, str]:
        """Return the text and the name of what wrote it (a model id, or "rules")."""
        ...
