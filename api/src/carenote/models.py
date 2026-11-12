"""Import every model so Base.metadata is complete (used by Alembic and tests)."""

from carenote.audit.models import AuditEvent
from carenote.auth.models import Role, User
from carenote.notes.models import ConfirmedObservation, Extraction, NoteStatus, VoiceNote
from carenote.patients.models import Patient

__all__ = [
    "AuditEvent",
    "ConfirmedObservation",
    "Extraction",
    "NoteStatus",
    "Patient",
    "Role",
    "User",
    "VoiceNote",
]
