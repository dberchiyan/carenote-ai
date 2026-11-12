import datetime as dt
import uuid

from pydantic import BaseModel

from carenote.contracts.handover import MedicationFact, Priority, VitalFact


class HandoverPatientOut(BaseModel):
    patient_id: uuid.UUID
    given_name: str
    family_name: str
    room: str
    priority: Priority
    summary: str
    vitals: list[VitalFact]
    symptoms: list[str]
    medications: list[MedicationFact]
    notes_confirmed: int
    open_drafts: int


class HandoverOut(BaseModel):
    ward: str
    hours: int
    since: dt.datetime
    until: dt.datetime
    summary: str
    # "rules" for the keyless writer, otherwise the model that wrote the text.
    written_by: str
    counts: dict[str, int]
    unassigned_drafts: int
    patients: list[HandoverPatientOut]
