from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from carenote.audit.models import AuditEvent
from carenote.contracts.llm import ExtractionResult, Prompt, ProviderError
from carenote.patients.synthetic import generate_patients
from carenote.providers.factory import get_llm
from carenote.providers.fake import RuleBasedLLM
from tests.conftest import login

PATIENTS = {p.full_name: p for p in generate_patients()}
NOTE = "Mrs. Anna Keller, BP 150/90, pulse 88. Complains of a headache. Gave 500 mg paracetamol PO."


def create(client: TestClient, text: str = NOTE) -> dict[str, Any]:
    response = client.post("/notes/text", json={"text": text})
    assert response.status_code == 202, response.text
    note = client.get(f"/notes/{response.json()['id']}").json()
    assert isinstance(note, dict)
    return note


def test_text_note_runs_the_pipeline_into_review(client: TestClient) -> None:
    note = create(login(client, "nurse"))
    assert note["status"] == "in_review"
    assert note["patient_id"] == str(PATIENTS["Anna Keller"].id)
    assert note["match_status"] == "matched"
    draft = note["draft"]
    assert isinstance(draft, dict)
    assert draft["version"] == 1
    assert draft["source"] == "ai"
    assert draft["prompt_version"] == "extract_v1"
    assert draft["flags"]["systolic_bp"] == "warning"
    # The nurse sees the original words, not the placeholders the LLM saw.
    assert draft["payload"]["patient_mention"] == "Mrs. Anna Keller"
    assert set(note["timings_ms"]) >= {"match", "redact", "extract", "validate", "flag"}


def test_redacted_transcript_and_mapping_are_not_exposed(client: TestClient) -> None:
    note = create(login(client, "nurse"))
    assert "redaction_map" not in note
    assert "redacted_transcript" not in note


def test_ambiguous_note_leaves_patient_unselected(client: TestClient) -> None:
    note = create(login(client, "nurse"), "Mrs. Keller, temperature 38.2.")
    assert note["status"] == "in_review"
    assert note["match_status"] == "ambiguous"
    assert note["patient_id"] is None
    assert len(note["candidates"]) >= 2


def test_note_creation_is_audited(client: TestClient, db: Session) -> None:
    note = create(login(client, "nurse"))
    events = db.scalars(select(AuditEvent).where(AuditEvent.entity_id == note["id"])).all()
    assert [e.action for e in events] == ["note.create"]


def test_nurse_sees_only_own_notes_and_charge_sees_ward(client: TestClient) -> None:
    note = create(login(client, "nurse"))
    login(client, "nurse_b")
    assert client.get(f"/notes/{note['id']}").status_code == 403
    assert client.get("/notes").json() == []
    login(client, "charge")
    assert client.get(f"/notes/{note['id']}").status_code == 200
    assert [n["id"] for n in client.get("/notes").json()] == [note["id"]]


def test_auditor_cannot_create_notes(client: TestClient) -> None:
    assert login(client, "auditor").post("/notes/text", json={"text": NOTE}).status_code == 403


def test_nurse_cannot_attach_a_patient_from_another_ward(client: TestClient) -> None:
    other = PATIENTS["Peter Braun"]
    response = login(client, "nurse").post(
        "/notes/text", json={"text": "pulse 80", "patient_id": str(other.id)}
    )
    assert response.status_code == 403


class FlakyLLM:
    name = "flaky"

    def __init__(self) -> None:
        self.calls = 0
        self.inner = RuleBasedLLM()

    def extract(self, redacted_text: str, prompt: Prompt) -> ExtractionResult:
        self.calls += 1
        if self.calls == 1:
            raise ProviderError("Anthropic API error 529: overloaded")
        return self.inner.extract(redacted_text, prompt)


def test_failure_is_recoverable_with_retry(client: TestClient) -> None:
    flaky = FlakyLLM()
    client.app.dependency_overrides[get_llm] = lambda: flaky  # type: ignore[attr-defined]
    note = create(login(client, "nurse"))
    assert note["status"] == "transcribed"
    assert note["error_step"] == "extract"
    assert "overloaded" in str(note["error_message"])

    assert client.post(f"/notes/{note['id']}/retry").status_code == 202
    retried = client.get(f"/notes/{note['id']}").json()
    assert retried["status"] == "in_review"
    assert retried["error_step"] is None
