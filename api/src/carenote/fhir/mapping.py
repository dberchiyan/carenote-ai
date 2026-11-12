"""Map patients and confirmed observations to FHIR R4 resources, in code (not by the LLM).

Models come from `fhir.resources.R4B`: the library no longer ships R4 (4.0.1) models, and
Patient/Observation/Bundle are structurally identical between R4 and R4B for what we emit.
R4 conformance is checked against a HAPI FHIR R4 server (`$validate`) in an integration test.
"""

import html
import uuid
from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any, Protocol

from fhir.resources.R4B.bundle import Bundle

from carenote.alerts.rules import Flag, RuleSet
from carenote.clinical.vitals import BP_PANEL_LOINC, VITALS, VitalKind

LOINC = "http://loinc.org"
UCUM = "http://unitsofmeasure.org"
CATEGORY = "http://terminology.hl7.org/CodeSystem/observation-category"
INTERPRETATION = "http://terminology.hl7.org/CodeSystem/v3-ObservationInterpretation"
MRN_SYSTEM = "urn:carenote:synthetic-mrn"
INTERPRETATION_DISPLAY = {
    "N": "Normal",
    "H": "High",
    "L": "Low",
    "HH": "Critical high",
    "LL": "Critical low",
}


class PatientLike(Protocol):
    @property
    def id(self) -> uuid.UUID: ...
    @property
    def mrn(self) -> str: ...
    @property
    def given_name(self) -> str: ...
    @property
    def family_name(self) -> str: ...
    @property
    def sex(self) -> str: ...
    @property
    def birth_date(self) -> Any: ...


class ObservationLike(Protocol):
    @property
    def id(self) -> uuid.UUID: ...
    @property
    def note_id(self) -> uuid.UUID: ...
    @property
    def kind(self) -> str: ...
    @property
    def value(self) -> float: ...
    @property
    def effective_at(self) -> datetime: ...
    @property
    def flag(self) -> str: ...


def _coding(system: str, code: str, display: str) -> dict[str, Any]:
    return {"coding": [{"system": system, "code": code, "display": display}], "text": display}


def _quantity(kind: VitalKind, value: float) -> dict[str, Any]:
    spec = VITALS[kind]
    return {"value": value, "unit": spec.unit_label, "system": UCUM, "code": spec.ucum}


def _flag(o: ObservationLike) -> Flag:
    """The flag confirmed with the observation; the export never re-judges a stored value."""
    return o.flag if o.flag in ("normal", "warning", "critical") else "normal"  # type: ignore[return-value]


def _interpretation(rules: RuleSet, o: ObservationLike) -> list[dict[str, Any]] | None:
    kind: VitalKind = o.kind  # type: ignore[assignment]
    code = rules.interpretation(kind, o.value, _flag(o))
    if code is None:
        return None
    return [_coding(INTERPRETATION, code, INTERPRETATION_DISPLAY[code])]


def _narrative(text: str) -> dict[str, str]:
    return {
        "status": "generated",
        "div": f'<div xmlns="http://www.w3.org/1999/xhtml">{html.escape(text)}</div>',
    }


def _describe(o: ObservationLike, rules: RuleSet) -> str:
    kind: VitalKind = o.kind  # type: ignore[assignment]
    spec = VITALS[kind]
    code = rules.interpretation(kind, o.value, _flag(o))
    suffix = f" ({INTERPRETATION_DISPLAY[code]})" if code else ""
    return f"{spec.display}: {o.value:g} {spec.unit_label}{suffix}"


def patient_resource(p: PatientLike) -> dict[str, Any]:
    return {
        "resourceType": "Patient",
        "id": str(p.id),
        "text": _narrative(
            f"{p.given_name} {p.family_name}, born {p.birth_date.isoformat()}, "
            f"MRN {p.mrn} (synthetic test patient)"
        ),
        "meta": {
            "tag": [
                {
                    "system": "urn:carenote:tags",
                    "code": "synthetic",
                    "display": "Synthetic test data",
                }
            ]
        },
        "identifier": [{"system": MRN_SYSTEM, "value": p.mrn}],
        "name": [{"use": "official", "family": p.family_name, "given": [p.given_name]}],
        "gender": p.sex if p.sex in ("male", "female", "other") else "unknown",
        "birthDate": p.birth_date.isoformat(),
    }


def _base_observation(
    obs_id: str,
    kind_code: dict[str, Any],
    vital_sign: bool,
    patient_ref: str,
    effective: datetime,
    narrative: str,
    performer: str | None,
) -> dict[str, Any]:
    category = ("vital-signs", "Vital Signs") if vital_sign else ("laboratory", "Laboratory")
    resource: dict[str, Any] = {
        "resourceType": "Observation",
        "id": obs_id,
        "text": _narrative(narrative),
        "status": "final",
        "category": [_coding(CATEGORY, *category)],
        "code": kind_code,
        "subject": {"reference": patient_ref},
        "effectiveDateTime": effective.isoformat(),
    }
    if performer:
        # The nurse who confirmed the value; a display-only reference keeps staff out of the bundle.
        resource["performer"] = [{"display": performer}]
    return resource


def observation_resources(
    observations: Sequence[ObservationLike],
    patient_ref: str,
    rules: RuleSet,
    performers: Mapping[uuid.UUID, str] | None = None,
) -> list[dict[str, Any]]:
    """One Observation per value; systolic + diastolic from the same note become a BP panel."""
    performers = performers or {}
    resources: list[dict[str, Any]] = []
    bp: dict[tuple[uuid.UUID, datetime], dict[str, ObservationLike]] = defaultdict(dict)
    for o in observations:
        if o.kind in ("systolic_bp", "diastolic_bp"):
            bp[(o.note_id, o.effective_at)][o.kind] = o
            continue
        kind: VitalKind = o.kind  # type: ignore[assignment]
        spec = VITALS[kind]
        resource = _base_observation(
            str(o.id),
            _coding(LOINC, spec.loinc, spec.display),
            spec.vital_sign,
            patient_ref,
            o.effective_at,
            _describe(o, rules),
            performers.get(o.note_id),
        )
        resource["valueQuantity"] = _quantity(kind, o.value)
        if (interp := _interpretation(rules, o)) is not None:
            resource["interpretation"] = interp
        resources.append(resource)

    for (_, effective), parts in bp.items():
        if set(parts) != {"systolic_bp", "diastolic_bp"}:
            # A lone systolic or diastolic value is still exported, as its own Observation.
            for kind_name, o in parts.items():
                k: VitalKind = kind_name  # type: ignore[assignment]
                resource = _base_observation(
                    str(o.id),
                    _coding(LOINC, VITALS[k].loinc, VITALS[k].display),
                    True,
                    patient_ref,
                    effective,
                    _describe(o, rules),
                    performers.get(o.note_id),
                )
                resource["valueQuantity"] = _quantity(k, o.value)
                resources.append(resource)
            continue
        systolic, diastolic = parts["systolic_bp"], parts["diastolic_bp"]
        panel = _base_observation(
            str(systolic.id),  # stable id: reuse the systolic row's id
            _coding(LOINC, BP_PANEL_LOINC, "Blood pressure panel with all children optional"),
            True,
            patient_ref,
            effective,
            f"Blood pressure {systolic.value:g}/{diastolic.value:g} mmHg",
            performers.get(systolic.note_id),
        )
        panel["component"] = []
        for k, o in (("systolic_bp", systolic), ("diastolic_bp", diastolic)):
            component: dict[str, Any] = {
                "code": _coding(LOINC, VITALS[k].loinc, VITALS[k].display),
                "valueQuantity": _quantity(k, o.value),
            }
            if (interp := _interpretation(rules, o)) is not None:
                component["interpretation"] = interp
            panel["component"].append(component)
        resources.append(panel)
    return resources


def transaction_bundle(
    patient: PatientLike,
    observations: Sequence[ObservationLike],
    rules: RuleSet,
    performers: Mapping[uuid.UUID, str] | None = None,
) -> dict[str, Any]:
    """A FHIR R4 transaction Bundle (Patient + Observations), validated with fhir.resources."""
    patient_url = f"urn:uuid:{patient.id}"
    entries = [
        {
            "fullUrl": patient_url,
            "resource": patient_resource(patient),
            "request": {"method": "PUT", "url": f"Patient/{patient.id}"},
        }
    ]
    for resource in observation_resources(observations, patient_url, rules, performers):
        entries.append(
            {
                "fullUrl": f"urn:uuid:{resource['id']}",
                "resource": resource,
                "request": {"method": "PUT", "url": f"Observation/{resource['id']}"},
            }
        )
    bundle = {"resourceType": "Bundle", "type": "transaction", "entry": entries}
    # Structural validation of every resource; raises if the mapping produced something invalid.
    Bundle.model_validate(bundle)
    return bundle
