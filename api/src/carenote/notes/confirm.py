"""Confirmation: the only code path that writes ConfirmedObservation rows."""

from datetime import datetime

from carenote.alerts.rules import RuleSet
from carenote.clinical.vitals import VITALS
from carenote.contracts.extraction import Extraction
from carenote.notes.models import ConfirmedObservation, VoiceNote


def observations_for(
    note: VoiceNote, extraction: Extraction, rules: RuleSet, effective_at: datetime
) -> list[ConfirmedObservation]:
    if note.patient_id is None:
        raise ValueError("A patient must be selected before confirming")
    return [
        ConfirmedObservation(
            note_id=note.id,
            patient_id=note.patient_id,
            kind=v.kind,
            code=VITALS[v.kind].loinc,
            value=v.value,
            unit=VITALS[v.kind].ucum,
            effective_at=effective_at,
            flag=rules.flag(v.kind, v.value),
            rules_version=rules.version,
        )
        for v in extraction.vitals
    ]
