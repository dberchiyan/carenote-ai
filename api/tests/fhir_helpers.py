import datetime as dt
import uuid
from dataclasses import dataclass

from carenote.alerts.rules import default_rules
from carenote.patients.synthetic import generate_patients

ANNA = next(p for p in generate_patients() if p.full_name == "Anna Keller")
NOTE_ID = uuid.uuid4()
WHEN = dt.datetime(2026, 11, 10, 14, 0, tzinfo=dt.UTC)


@dataclass
class Obs:
    kind: str
    value: float
    id: uuid.UUID
    note_id: uuid.UUID = NOTE_ID
    effective_at: dt.datetime = WHEN
    flag: str = "normal"

    def __post_init__(self) -> None:
        if self.flag == "normal":  # default: what confirming under the current rules stores
            self.flag = default_rules().flag(self.kind, self.value)  # type: ignore[arg-type]


def sample_observations() -> list[Obs]:
    return [
        Obs("systolic_bp", 168, uuid.uuid4()),
        Obs("diastolic_bp", 96, uuid.uuid4()),
        Obs("heart_rate", 88, uuid.uuid4()),
        Obs("temperature", 38.4, uuid.uuid4()),
        Obs("spo2", 87, uuid.uuid4()),
        Obs("respiratory_rate", 18, uuid.uuid4()),
        Obs("weight", 72.5, uuid.uuid4()),
        Obs("blood_glucose", 62, uuid.uuid4()),
    ]
