"""The keyless handover writer: short, factual sentences built from the facts by rule.

An LLM writer (providers/anthropic_handover.py) can replace it; both return the same shape.
Neither gives clinical advice: the text restates values, flags, symptoms and medications.
"""

from carenote.contracts.handover import (
    HandoverFacts,
    HandoverText,
    PatientFacts,
    RoomSummary,
    VitalFact,
)

RULES_WRITER = "rules"


def _num(value: float) -> str:
    return f"{value:g}"


def _vital(v: VitalFact) -> str:
    unit = v.unit if v.unit in ("%", "°C") else f" {v.unit}"
    text = f"{v.label} {_num(v.value)}{unit}"
    if v.flag != "normal":
        text += f" ({v.flag}"
        if v.change == "new_flag":
            text += ", new"
        elif v.change == "worse":
            text += ", worse"
        if v.previous is not None:
            text += f", was {_num(v.previous)}"
        text += ")"
    elif v.worst_in_shift != "normal":
        text += f" (back to normal, was {v.worst_in_shift} this shift)"
    elif v.change == "better" and v.previous is not None:
        text += f" (improved from {_num(v.previous)})"
    return text


def _bp(vitals: list[VitalFact]) -> list[VitalFact]:
    """Systolic and diastolic as one reading: "BP 152/94 mmHg (warning)"."""
    by_kind = {v.kind: v for v in vitals}
    sys, dia = by_kind.get("systolic_bp"), by_kind.get("diastolic_bp")
    if not (sys and dia):
        return vitals
    worse = sys if (sys.flag, sys.worst_in_shift) >= (dia.flag, dia.worst_in_shift) else dia
    merged = worse.model_copy(
        update={
            "label": "BP",
            "kind": "bp",
            "value": sys.value,
            "previous": sys.previous,
        }
    )
    out: list[VitalFact] = []
    for v in vitals:
        if v.kind == "systolic_bp":
            out.append(merged)
        elif v.kind != "diastolic_bp":
            out.append(v)
    return out


def _bp_text(v: VitalFact, vitals: list[VitalFact]) -> str:
    dia = next((x for x in vitals if x.kind == "diastolic_bp"), None)
    text = _vital(v)
    if v.kind == "bp" and dia is not None:
        text = text.replace(f"BP {_num(v.value)}", f"BP {_num(v.value)}/{_num(dia.value)}", 1)
    return text


def patient_summary(p: PatientFacts) -> str:
    sentences: list[str] = []
    vitals = _bp(p.vitals)
    flagged = [v for v in vitals if v.flag != "normal" or v.worst_in_shift != "normal"]
    if flagged:
        sentences.append(", ".join(_bp_text(v, p.vitals) for v in flagged) + ".")
        rest = [v for v in vitals if v not in flagged][:3]
        if rest:
            sentences.append("Otherwise " + ", ".join(_bp_text(v, p.vitals) for v in rest) + ".")
    elif vitals:
        sentences.append("Stable: " + ", ".join(_bp_text(v, p.vitals) for v in vitals[:4]) + ".")
    else:
        sentences.append("No confirmed observations this shift.")
    if p.symptoms:
        sentences.append("Reports " + ", ".join(p.symptoms) + ".")
    if p.medications:
        given = [
            " ".join(part for part in (m.name, m.dose, m.route) if part) for m in p.medications
        ]
        sentences.append("Given " + "; ".join(given) + ".")
    if p.open_drafts:
        s = "s" if p.open_drafts > 1 else ""
        sentences.append(f"{p.open_drafts} draft{s} awaiting review.")
    return " ".join(sentences)


def ward_summary(f: HandoverFacts) -> str:
    counts = {k: sum(1 for p in f.patients if p.priority == k) for k in ("critical", "warning")}
    new = sum(1 for p in f.patients for v in p.vitals if v.change in ("new_flag", "worse"))
    notes = sum(p.notes_confirmed for p in f.patients)
    drafts = sum(p.open_drafts for p in f.patients) + f.unassigned_drafts
    parts = [f"{len(f.patients)} patients on ward {f.ward}."]
    if counts["critical"] or counts["warning"]:
        flagged = []
        if counts["critical"]:
            flagged.append(f"{counts['critical']} critical")
        if counts["warning"]:
            flagged.append(f"{counts['warning']} warning")
        tail = f" ({new} new or worse since the last shift)" if new else ""
        parts.append(" and ".join(flagged).capitalize() + tail + ".")
    else:
        parts.append("No flagged values this shift.")
    parts.append(f"{notes} notes confirmed in the last {f.hours} h.")
    if drafts:
        parts.append(f"{drafts} draft{'s' if drafts > 1 else ''} awaiting review.")
    return " ".join(parts)


class RuleBasedHandoverWriter:
    name = RULES_WRITER

    def write(self, facts: HandoverFacts) -> tuple[HandoverText, str]:
        return (
            HandoverText(
                ward_summary=ward_summary(facts),
                patients=[
                    RoomSummary(room=p.room, summary=patient_summary(p)) for p in facts.patients
                ],
            ),
            RULES_WRITER,
        )
