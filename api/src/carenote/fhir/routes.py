import uuid
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import select

from carenote.alerts.rules import default_rules
from carenote.audit import service as audit
from carenote.auth.deps import CurrentUser, DbSession, current_user
from carenote.auth.models import User
from carenote.fhir.mapping import transaction_bundle
from carenote.notes.models import ConfirmedObservation, VoiceNote
from carenote.patients.access import get_patient_for

router = APIRouter(tags=["fhir"], dependencies=[Depends(current_user)])


@router.get(
    "/patients/{patient_id}/fhir",
    response_class=JSONResponse,
    responses={200: {"content": {"application/fhir+json": {}}}},
)
def export_fhir(patient_id: uuid.UUID, session: DbSession, user: CurrentUser) -> JSONResponse:
    """FHIR R4 transaction Bundle with the patient and all confirmed observations (audited)."""
    patient = get_patient_for(session, user, patient_id)
    observations = list(
        session.scalars(
            select(ConfirmedObservation)
            .where(ConfirmedObservation.patient_id == patient.id)
            .order_by(ConfirmedObservation.effective_at)
        )
    )
    performers = {
        note_id: f"{name} (registered nurse)"
        for note_id, name in session.execute(
            select(VoiceNote.id, User.display_name)
            .join(User, User.id == VoiceNote.confirmed_by)
            .where(VoiceNote.id.in_({o.note_id for o in observations}))
        )
    }
    bundle: dict[str, Any] = transaction_bundle(patient, observations, default_rules(), performers)
    audit.record(
        session,
        actor_id=user.id,
        action="fhir.export",
        entity="patient",
        entity_id=patient.id,
        after={"resources": len(bundle["entry"])},
    )
    session.commit()
    return JSONResponse(
        bundle,
        media_type="application/fhir+json",
        headers={"Content-Disposition": f'attachment; filename="patient-{patient.mrn}-fhir.json"'},
    )
