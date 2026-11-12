"""Vital sign kinds with LOINC codes, UCUM units and plausibility ranges.

The LLM never chooses codes or units: they are attached here, in code.
"""

from dataclasses import dataclass
from typing import Literal, get_args

VitalKind = Literal[
    "systolic_bp",
    "diastolic_bp",
    "heart_rate",
    "respiratory_rate",
    "temperature",
    "spo2",
    "weight",
    "blood_glucose",
]
VITAL_KINDS: tuple[VitalKind, ...] = get_args(VitalKind)

BP_PANEL_LOINC = "85354-9"


@dataclass(frozen=True)
class VitalSpec:
    kind: VitalKind
    loinc: str
    display: str
    ucum: str
    unit_label: str
    # Physiologically plausible range; values outside are treated as recording errors.
    plausible: tuple[float, float]
    vital_sign: bool = True  # blood glucose is a lab value in FHIR terms


VITALS: dict[VitalKind, VitalSpec] = {
    s.kind: s
    for s in (
        VitalSpec("systolic_bp", "8480-6", "Systolic blood pressure", "mm[Hg]", "mmHg", (40, 300)),
        VitalSpec(
            "diastolic_bp", "8462-4", "Diastolic blood pressure", "mm[Hg]", "mmHg", (20, 200)
        ),
        VitalSpec("heart_rate", "8867-4", "Heart rate", "/min", "/min", (20, 250)),
        VitalSpec("respiratory_rate", "9279-1", "Respiratory rate", "/min", "/min", (4, 70)),
        VitalSpec("temperature", "8310-5", "Body temperature", "Cel", "°C", (30, 44)),
        VitalSpec("spo2", "59408-5", "Oxygen saturation", "%", "%", (50, 100)),
        VitalSpec("weight", "29463-7", "Body weight", "kg", "kg", (1, 400)),
        VitalSpec(
            "blood_glucose",
            "2339-0",
            "Glucose [Mass/volume] in Blood",
            "mg/dL",
            "mg/dL",
            (10, 1000),
            vital_sign=False,
        ),
    )
}
