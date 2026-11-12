"""What nurses change in AI drafts. Pure functions over two extraction versions.

Every edit before Confirm is free ground truth: the nurse heard the dictation and fixed the
draft. Aggregated, edits show which fields the model gets wrong; exported, they become eval cases.
"""

from typing import Any, Literal

from pydantic import BaseModel

from carenote.contracts.extraction import Extraction, Medication

Change = Literal["added", "removed", "changed"]


class FieldChange(BaseModel):
    field: str  # a vital kind, "symptom" or "medication"
    change: Change
    before: str | None
    after: str | None


def _med(m: Medication) -> str:
    return " ".join(x for x in (m.dose, m.route) if x) or m.name


def diff_extractions(ai: Extraction, final: Extraction) -> list[FieldChange]:
    changes: list[FieldChange] = []
    before = {v.kind: v.value for v in ai.vitals}
    after = {v.kind: v.value for v in final.vitals}
    for kind in sorted(before.keys() | after.keys()):
        b, a = before.get(kind), after.get(kind)
        if b is None:
            changes.append(FieldChange(field=kind, change="added", before=None, after=f"{a:g}"))
        elif a is None:
            changes.append(FieldChange(field=kind, change="removed", before=f"{b:g}", after=None))
        elif abs(a - b) > 1e-9:
            changes.append(
                FieldChange(field=kind, change="changed", before=f"{b:g}", after=f"{a:g}")
            )
    for s in sorted(set(final.symptoms) - set(ai.symptoms)):
        changes.append(FieldChange(field="symptom", change="added", before=None, after=s))
    for s in sorted(set(ai.symptoms) - set(final.symptoms)):
        changes.append(FieldChange(field="symptom", change="removed", before=s, after=None))
    meds_before = {m.name: m for m in ai.medications}
    meds_after = {m.name: m for m in final.medications}
    for name in sorted(meds_before.keys() | meds_after.keys()):
        mb, ma = meds_before.get(name), meds_after.get(name)
        if mb is None and ma is not None:
            changes.append(
                FieldChange(
                    field="medication", change="added", before=None, after=f"{name} {_med(ma)}"
                )
            )
        elif ma is None and mb is not None:
            changes.append(
                FieldChange(
                    field="medication", change="removed", before=f"{name} {_med(mb)}", after=None
                )
            )
        elif mb is not None and ma is not None and (mb.dose, mb.route) != (ma.dose, ma.route):
            changes.append(
                FieldChange(
                    field="medication",
                    change="changed",
                    before=f"{name} {_med(mb)}",
                    after=f"{name} {_med(ma)}",
                )
            )
    return changes


def eval_case(
    case_id: str, ward: str, redacted_text: str, final: Extraction, changes: list[FieldChange]
) -> dict[str, Any]:
    """An eval case in the `evals/data/*.jsonl` format. The text stays redacted: names are not
    needed to grade extraction, and the export must not carry identifiers."""
    return {
        "id": case_id,
        "tags": ["nurse_correction", *sorted({f"corrected_{c.field}" for c in changes})],
        "difficulty": "hard",
        "ward": ward,
        "text": redacted_text,
        "expected_patient_id": None,
        "expected_patient_candidates": [],
        "expected_vitals": [
            {"kind": v.kind, "value": v.value, "unit": v.unit} for v in final.vitals
        ],
        "expected_symptoms": final.symptoms,
        "expected_medications": [
            {"name": m.name, "dose": m.dose, "route": m.route} for m in final.medications
        ],
        "expected_uncertain_kinds": [],
        "notes": [f"{c.field}: AI {c.before or '—'} → nurse {c.after or '—'}" for c in changes],
        "audio_file": "",
    }
