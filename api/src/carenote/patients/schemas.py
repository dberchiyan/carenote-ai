import datetime as dt
import uuid

from pydantic import BaseModel, ConfigDict


class PatientOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    mrn: str
    given_name: str
    family_name: str
    birth_date: dt.date
    sex: str
    ward: str
    room: str


class LatestVitalOut(BaseModel):
    kind: str
    value: float
    unit: str
    flag: str
    effective_at: dt.datetime


class WardPatientOut(PatientOut):
    latest_vitals: list[LatestVitalOut]
    open_drafts: int


class ObservationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    note_id: uuid.UUID
    kind: str
    code: str
    value: float
    unit: str
    flag: str
    effective_at: dt.datetime
