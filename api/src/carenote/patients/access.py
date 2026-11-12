"""Who may see a patient."""

import uuid

from sqlalchemy.orm import Session

from carenote.auth.deps import ensure_ward_access
from carenote.auth.models import User
from carenote.errors import not_found
from carenote.patients.models import Patient


def get_patient_for(session: Session, user: User, patient_id: uuid.UUID) -> Patient:
    """Load a patient and enforce ward access (403 for another ward, 404 when unknown)."""
    patient = session.get(Patient, patient_id)
    if patient is None:
        raise not_found("Patient", patient_id=str(patient_id))
    ensure_ward_access(user, patient.ward)
    return patient
