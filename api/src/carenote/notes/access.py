"""Who may see or change a note."""

import uuid

from sqlalchemy import ColumnElement, true
from sqlalchemy.orm import Session

from carenote.auth.deps import ensure_ward_access
from carenote.auth.models import Role, User
from carenote.errors import forbidden, not_found
from carenote.notes.models import VoiceNote


def note_scope(user: User) -> ColumnElement[bool]:
    """The WHERE clause that narrows `VoiceNote` to what the caller may see: nurses their own
    notes, charge nurses their ward, auditors everything. The one place the rule is written."""
    if user.role is Role.NURSE:
        return VoiceNote.author_id == user.id
    if user.role is Role.CHARGE_NURSE:
        return VoiceNote.ward == user.ward
    return true()


def get_note_for(session: Session, user: User, note_id: uuid.UUID, *, write: bool) -> VoiceNote:
    """Nurses: own notes on their ward. Charge nurses: every note of their ward.
    Auditors: read-only on every ward. A write locks the row for the transaction, so two
    concurrent confirms or edits are serialised instead of both passing the state check."""
    note = session.get(VoiceNote, note_id, with_for_update=write)
    if note is None:
        raise not_found("Note", note_id=str(note_id))
    if user.role is Role.AUDITOR:
        if write:
            raise forbidden("Auditors have read-only access")
        return note
    ensure_ward_access(user, note.ward)
    if user.role is Role.NURSE and note.author_id != user.id:
        raise forbidden("Not your note")
    return note
