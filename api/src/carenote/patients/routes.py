import datetime as dt
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select

from carenote.auth.deps import CurrentUser, DbSession, current_user, ensure_ward_access
from carenote.auth.models import Role
from carenote.db import utcnow
from carenote.errors import forbidden
from carenote.notes.models import ConfirmedObservation, NoteStatus, VoiceNote
from carenote.pagination import Page, PageParams, count, page, page_params
from carenote.patients.access import get_patient_for
from carenote.patients.models import Patient
from carenote.patients.schemas import LatestVitalOut, ObservationOut, PatientOut, WardPatientOut

router = APIRouter(prefix="/patients", tags=["patients"], dependencies=[Depends(current_user)])


@router.get("")
def list_patients(
    session: DbSession, user: CurrentUser, ward: str | None = None
) -> list[WardPatientOut]:
    """Patients of a ward with their latest confirmed vitals. Defaults to the caller's ward."""
    ward = ward or user.ward
    if ward is None:
        if user.role is not Role.AUDITOR:
            raise forbidden("No ward assigned")
        rows = session.scalars(select(Patient).order_by(Patient.ward, Patient.room)).all()
    else:
        ensure_ward_access(user, ward)
        rows = session.scalars(
            select(Patient).where(Patient.ward == ward).order_by(Patient.room)
        ).all()
    return _with_latest(session, list(rows))


def _with_latest(session: DbSession, patients: list[Patient]) -> list[WardPatientOut]:
    ids = [p.id for p in patients]
    # Newest row per (patient, kind): DISTINCT ON over the (patient_id, kind, effective_at)
    # index, instead of loading the ward's whole history to keep the last of each.
    latest: dict[tuple[str, str], ConfirmedObservation] = {}
    observations = session.scalars(
        select(ConfirmedObservation)
        .distinct(ConfirmedObservation.patient_id, ConfirmedObservation.kind)
        .where(ConfirmedObservation.patient_id.in_(ids))
        .order_by(
            ConfirmedObservation.patient_id,
            ConfirmedObservation.kind,
            ConfirmedObservation.effective_at.desc(),
        )
    )
    for o in observations:
        latest[(str(o.patient_id), o.kind)] = o
    drafts: dict[str, int] = {}
    for pid in session.scalars(
        select(VoiceNote.patient_id).where(
            VoiceNote.patient_id.in_(ids), VoiceNote.status == NoteStatus.IN_REVIEW
        )
    ):
        drafts[str(pid)] = drafts.get(str(pid), 0) + 1
    return [
        WardPatientOut(
            **PatientOut.model_validate(p).model_dump(),
            latest_vitals=[
                LatestVitalOut(
                    kind=o.kind,
                    value=o.value,
                    unit=o.unit,
                    flag=o.flag,
                    effective_at=o.effective_at,
                )
                for (pid, _), o in latest.items()
                if pid == str(p.id)
            ],
            open_drafts=drafts.get(str(p.id), 0),
        )
        for p in patients
    ]


@router.get("/{patient_id}")
def get_patient(patient_id: uuid.UUID, session: DbSession, user: CurrentUser) -> PatientOut:
    return PatientOut.model_validate(get_patient_for(session, user, patient_id))


@router.get("/{patient_id}/observations")
def list_observations(
    patient_id: uuid.UUID,
    session: DbSession,
    user: CurrentUser,
    paging: Annotated[PageParams, Depends(page_params(default_limit=500, max_limit=2000))],
    days: Annotated[int, Query(ge=1, le=365)] = 30,
) -> Page[ObservationOut]:
    """Confirmed observations of the last `days` days, oldest first."""
    patient = get_patient_for(session, user, patient_id)
    query = select(ConfirmedObservation).where(
        ConfirmedObservation.patient_id == patient.id,
        ConfirmedObservation.effective_at >= utcnow() - dt.timedelta(days=days),
    )
    rows = session.scalars(
        query.order_by(ConfirmedObservation.effective_at, ConfirmedObservation.kind)
        .limit(paging.limit)
        .offset(paging.offset)
    )
    return page([ObservationOut.model_validate(o) for o in rows], count(session, query), paging)
