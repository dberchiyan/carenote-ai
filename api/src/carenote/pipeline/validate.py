"""Validate and normalize an extraction: UCUM units, plausibility, duplicates.

Implausible values are moved to `uncertain` with an explanation — never silently dropped.
"""

import re

from carenote.clinical.vitals import VITALS, VitalKind
from carenote.contracts.extraction import Extraction, Medication, Vital

_ROUTE_ALIASES = {
    "po": "oral", "p.o.": "oral", "by mouth": "oral", "orally": "oral", "oral": "oral",
    "iv": "iv", "i.v.": "iv", "intravenous": "iv", "intravenously": "iv",
    "sc": "subcutaneous", "s.c.": "subcutaneous", "subcut": "subcutaneous",
    "subcutaneous": "subcutaneous", "subcutaneously": "subcutaneous", "sq": "subcutaneous",
    "inhaled": "inhaled", "inhalation": "inhaled", "nebulised": "inhaled", "nebulized": "inhaled",
    "im": "intramuscular", "i.m.": "intramuscular", "intramuscular": "intramuscular",
}  # fmt: skip
_DOSE = re.compile(
    r"^\s*(\d+(?:\.\d+)?)\s*(mg|milligrams?|g|grams?|mcg|micrograms?|units?|puffs?|ml)\s*$", re.I
)
_DOSE_UNITS = {"milligram": "mg", "gram": "g", "microgram": "mcg", "unit": "units", "puff": "puffs"}


def normalize_unit(kind: VitalKind, value: float, unit: str) -> tuple[float, str]:
    """Convert to the UCUM unit for `kind`. Returns (value, ucum)."""
    u = unit.strip().lower().replace("°", "")
    if kind == "temperature" and (u in {"f", "fahrenheit", "degf", "[degf]"} or u.endswith(" f")):
        return round((value - 32) * 5 / 9, 1), "Cel"
    if kind == "weight" and u in {"lb", "lbs", "pound", "pounds", "[lb_av]"}:
        return round(value * 0.45359237, 1), "kg"
    if kind == "blood_glucose" and ("mmol" in u or "millimol" in u):
        return round(value * 18.016), "mg/dL"
    return value, VITALS[kind].ucum


def _normalize_dose(dose: str | None) -> str | None:
    if dose is None:
        return None
    m = _DOSE.match(dose)
    if not m:
        return dose.strip()
    amount, unit = m.group(1), m.group(2).lower().rstrip("s")
    unit = _DOSE_UNITS.get(unit, unit)
    amount = amount.rstrip("0").rstrip(".") if "." in amount else amount
    return f"{amount} {unit}"


def _normalize_medication(med: Medication) -> Medication:
    route = med.route.strip().lower() if med.route else None
    return med.model_copy(
        update={
            "name": med.name.strip().lower(),
            "dose": _normalize_dose(med.dose),
            "route": _ROUTE_ALIASES.get(route, route) if route else None,
        }
    )


def validate_extraction(extraction: Extraction) -> Extraction:
    uncertain = list(extraction.uncertain)
    vitals: dict[VitalKind, Vital] = {}
    for vital in extraction.vitals:
        spec = VITALS[vital.kind]
        value, unit = normalize_unit(vital.kind, vital.value, vital.unit)
        lo, hi = spec.plausible
        if not lo <= value <= hi:
            uncertain.append(
                f"Implausible {spec.display.lower()} {vital.value:g} {vital.unit} "
                f'("{vital.source_text}") — not added; please re-measure or correct.'
            )
            continue
        if vital.kind in vitals and vitals[vital.kind].value != value:
            uncertain.append(
                f"Several values for {spec.display.lower()}; kept the last one ({value:g} {unit})."
            )
        vitals[vital.kind] = vital.model_copy(update={"value": value, "unit": unit})

    symptoms = list(dict.fromkeys(s.strip().lower() for s in extraction.symptoms if s.strip()))
    return extraction.model_copy(
        update={
            "vitals": list(vitals.values()),
            "symptoms": symptoms,
            "medications": [_normalize_medication(m) for m in extraction.medications],
            "uncertain": list(dict.fromkeys(uncertain)),
        }
    )
