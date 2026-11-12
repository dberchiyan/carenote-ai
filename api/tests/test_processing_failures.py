"""A note must never get stuck: unexpected errors are recorded, stalled notes can be retried, and
concurrent writes are refused rather than duplicated."""

import uuid
from datetime import timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Connection, Engine, insert, select, text, update
from sqlalchemy.orm import Session

from carenote.db import utcnow
from carenote.notes import processing, routes, service
from carenote.notes.models import Extraction, NoteStatus, VoiceNote
from carenote.pipeline.validate import validate_extraction
from tests.conftest import login


def create(client: TestClient, text: str = "Mrs. Anna Keller, pulse 80.") -> dict[str, Any]:
    note_id = client.post("/notes/text", json={"text": text}).json()["id"]
    result: dict[str, Any] = client.get(f"/notes/{note_id}").json()
    return result


def test_unexpected_error_is_recorded_and_retryable(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    login(client, "nurse")

    def boom(*_: Any, **__: Any) -> Any:
        raise RuntimeError("bug in the pipeline")

    monkeypatch.setattr(processing, "run_text_pipeline", boom)
    note = create(client)
    assert note["status"] == "transcribed"
    assert note["error_step"] == "extract"
    assert "Unexpected error" in note["error_message"]
    assert "RuntimeError" in note["error_message"]
    assert note["stalled"] is False

    monkeypatch.undo()
    assert client.post(f"/notes/{note['id']}/retry").status_code == 202
    assert client.get(f"/notes/{note['id']}").json()["status"] == "in_review"


def test_stalled_note_can_be_retried(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The worker died (no error recorded) and the note is older than the processing timeout."""
    login(client, "nurse")
    monkeypatch.setattr(routes, "process_note", lambda *a, **k: None)  # the job never ran
    note = create(client)
    assert note["status"] == "transcribed"
    assert note["error_step"] is None
    assert note["stalled"] is False
    assert client.post(f"/notes/{note['id']}/retry").status_code == 409  # still within the window

    db.execute(
        update(VoiceNote)
        .where(VoiceNote.id == uuid.UUID(note["id"]))
        .values(created_at=utcnow() - timedelta(minutes=10))
    )
    db.flush()
    assert client.get(f"/notes/{note['id']}").json()["stalled"] is True
    monkeypatch.undo()
    assert client.post(f"/notes/{note['id']}/retry").status_code == 202
    assert client.get(f"/notes/{note['id']}").json()["status"] == "in_review"


def test_concurrent_edit_is_refused_not_duplicated(
    client: TestClient, connection: Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Another save lands between load and commit: 409, not a 500 or a third copy."""
    login(client, "nurse")
    note = create(client)
    note_id = uuid.UUID(note["id"])

    def race(payload: Any) -> Any:
        connection.execute(
            insert(Extraction).values(
                id=uuid.uuid4(),
                note_id=note_id,
                version=2,
                payload=note["draft"]["payload"],
                source="nurse",
                created_at=utcnow(),
            )
        )
        return validate_extraction(payload)

    monkeypatch.setattr(service, "validate_extraction", race)
    response = client.patch(f"/notes/{note_id}/draft", json={"payload": note["draft"]["payload"]})
    assert response.status_code == 409
    assert "changed while you were editing" in response.json()["message"]
    versions = connection.scalars(
        select(Extraction.version).where(Extraction.note_id == note_id)
    ).all()
    assert 3 not in versions  # the losing edit was not stored


def test_write_access_locks_the_note_row(client: TestClient, db: Session) -> None:
    login(client, "nurse")
    note = create(client)
    stored = db.get(VoiceNote, uuid.UUID(note["id"]), with_for_update=True)
    assert stored is not None
    assert stored.status is NoteStatus.IN_REVIEW


def test_a_note_goes_straight_from_transcribed_to_review(
    client: TestClient, owner_engine: Engine
) -> None:
    """No intermediate `extracted` status: in the code, the schema and the database enum."""
    assert [s.value for s in NoteStatus] == [
        "uploaded",
        "transcribed",
        "in_review",
        "confirmed",
        "rejected",
    ]
    with owner_engine.connect() as conn:
        labels = conn.scalars(
            text(
                "SELECT e.enumlabel FROM pg_enum e JOIN pg_type t ON t.oid = e.enumtypid "
                "WHERE t.typname = 'note_status' ORDER BY e.enumsortorder"
            )
        ).all()
    assert list(labels) == [s.value for s in NoteStatus]
    login(client, "nurse")
    assert create(client)["status"] == "in_review"
