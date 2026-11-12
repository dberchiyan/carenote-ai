import json
import uuid
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from carenote.audit.models import AuditEvent
from carenote.config import Settings, get_settings
from carenote.notes.models import ConfirmedObservation, Extraction
from carenote.patients.synthetic import generate_patients
from carenote.providers.fake import FakeTranscription
from tests.conftest import login

FIXTURES = Path(__file__).parent / "fixtures"
PATIENTS = {p.full_name: p for p in generate_patients()}
ANNA, HANNA = PATIENTS["Anna Keller"], PATIENTS["Hanna Keller"]


@pytest.fixture(autouse=True)
def audio_dir(client: TestClient, tmp_path: Path) -> Path:
    settings = Settings(audio_dir=tmp_path, max_audio_seconds=120)
    client.app.dependency_overrides[get_settings] = lambda: settings  # type: ignore[attr-defined]
    # Background processing reads settings directly, not through FastAPI.
    get_settings.cache_clear()
    import os

    os.environ["CARENOTE_AUDIO_DIR"] = str(tmp_path)
    return tmp_path


def upload(client: TestClient, name: str = "note.wav", mime: str = "audio/wav", **form: str) -> Any:
    data = (FIXTURES / name).read_bytes()
    return client.post("/notes", files={"audio": (name, data, mime)}, data=form)


def test_a_browser_transcript_is_used_instead_of_the_transcription_provider(
    client: TestClient, db: Session
) -> None:
    """The nurse saw and corrected the on-device transcript; the server must not replace it
    with the provider's (in the keyless demo: a sample sentence about another patient)."""
    note_id = upload(login(client, "nurse"), transcript="John, 80 pulse, headache").json()["id"]
    note = client.get(f"/notes/{note_id}").json()
    assert note["status"] == "in_review"
    assert note["transcript"] == "John, 80 pulse, headache"
    assert note["transcription_model"] == "browser"
    assert {v["kind"]: v["value"] for v in note["draft"]["payload"]["vitals"]} == {"heart_rate": 80}
    assert note["draft"]["payload"]["symptoms"] == ["headache"]
    event = db.scalars(
        select(AuditEvent).where(AuditEvent.action == "note.upload").order_by(AuditEvent.at.desc())
    ).first()
    assert event is not None
    assert event.after is not None
    assert event.after["transcript"] == "browser"


def test_the_sample_transcript_is_labelled_as_such(client: TestClient) -> None:
    note_id = upload(login(client, "nurse")).json()["id"]
    assert client.get(f"/notes/{note_id}").json()["transcription_model"] == "fake-transcriber"


@pytest.mark.parametrize(("name", "mime"), [("note.wav", "audio/wav"), ("note.webm", "audio/webm")])
def test_audio_upload_is_transcribed_and_extracted(
    client: TestClient, audio_dir: Path, name: str, mime: str
) -> None:
    response = upload(login(client, "nurse"), name, mime)
    assert response.status_code == 202, response.text
    note = client.get(f"/notes/{response.json()['id']}").json()
    assert note["source"] == "audio"
    assert note["status"] == "in_review"
    assert note["transcript"].startswith("Mrs. Anna Keller")  # fake transcriber demo text
    assert note["patient_id"] == str(ANNA.id)
    assert list(audio_dir.iterdir())


def test_known_audio_gets_its_registered_transcript(
    client: TestClient, transcriber: FakeTranscription
) -> None:
    data = (FIXTURES / "note.wav").read_bytes()
    transcriber.known[transcriber.digest(data)] = "Hanna Keller, pulse 72."
    note_id = upload(login(client, "nurse")).json()["id"]
    assert client.get(f"/notes/{note_id}").json()["patient_id"] == str(HANNA.id)


@pytest.mark.parametrize(
    ("data", "mime", "message"),
    [
        (b"", "audio/wav", "empty"),
        (b"hello world, not audio", "audio/wav", "does not match"),
        ((FIXTURES / "note.wav").read_bytes(), "application/pdf", "Unsupported"),
        ((FIXTURES / "note.wav").read_bytes(), "audio/webm", "does not match"),
    ],
)
def test_bad_uploads_are_rejected(client: TestClient, data: bytes, mime: str, message: str) -> None:
    response = login(client, "nurse").post("/notes", files={"audio": ("x", data, mime)})
    assert response.status_code == 422
    assert message in response.json()["message"]


def test_too_long_and_too_large_uploads_are_rejected(client: TestClient, tmp_path: Path) -> None:
    settings = Settings(audio_dir=tmp_path, max_audio_seconds=1.0, max_upload_bytes=200_000)
    client.app.dependency_overrides[get_settings] = lambda: settings  # type: ignore[attr-defined]
    login(client, "nurse")
    long = upload(client)
    assert long.status_code == 422
    assert "at most 1 seconds" in long.json()["message"]
    big = client.post(
        "/notes", files={"audio": ("x.wav", b"RIFF\0\0\0\0WAVE" + b"\0" * 300_000, "audio/wav")}
    )
    assert big.status_code == 422
    assert "larger than" in big.json()["message"]


def text_note(client: TestClient, text: str) -> dict[str, Any]:
    note_id = client.post("/notes/text", json={"text": text}).json()["id"]
    result: dict[str, Any] = client.get(f"/notes/{note_id}").json()
    return result


def test_edit_confirm_writes_observations_and_audits(client: TestClient, db: Session) -> None:
    login(client, "nurse")
    note = text_note(client, "Mrs. Keller, BP 150/90, pulse 88. Complains of a headache.")
    assert note["patient_id"] is None  # ambiguous: Anna or Hanna

    # Confirm is refused until a patient is selected.
    assert client.post(f"/notes/{note['id']}/confirm", json={}).status_code == 409

    payload = note["draft"]["payload"]
    payload["vitals"] = [v for v in payload["vitals"] if v["kind"] != "heart_rate"]
    payload["vitals"].append(
        {"kind": "heart_rate", "value": 92, "unit": "/min", "source_text": "pulse 88"}
    )
    edited = client.patch(
        f"/notes/{note['id']}/draft", json={"payload": payload, "patient_id": str(HANNA.id)}
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["draft"]["version"] == 2
    assert edited.json()["draft"]["source"] == "nurse"
    assert db.scalars(select(ConfirmedObservation)).all() == []  # still only a draft

    confirmed = client.post(f"/notes/{note['id']}/confirm", json={})
    assert confirmed.status_code == 200
    assert confirmed.json()["status"] == "confirmed"

    observations = db.scalars(
        select(ConfirmedObservation).where(ConfirmedObservation.patient_id == HANNA.id)
    ).all()
    assert {(o.code, o.value, o.unit, o.flag) for o in observations} == {
        ("8480-6", 150, "mm[Hg]", "warning"),
        ("8462-4", 90, "mm[Hg]", "normal"),
        ("8867-4", 92, "/min", "normal"),
    }
    actions = [
        e.action
        for e in db.scalars(
            select(AuditEvent).where(AuditEvent.entity_id == note["id"]).order_by(AuditEvent.at)
        )
    ]
    assert actions == ["note.create", "note.draft_edit", "note.confirm"]
    edit = db.scalar(select(AuditEvent).where(AuditEvent.action == "note.draft_edit"))
    assert edit is not None
    assert edit.before is not None
    assert edit.after is not None
    assert edit.before["version"] == 1
    assert edit.after["version"] == 2

    # The ward view now shows the latest flagged vitals.
    ward = {p["id"]: p for p in client.get("/patients").json()}
    assert {v["kind"]: v["flag"] for v in ward[str(HANNA.id)]["latest_vitals"]}["systolic_bp"] == (
        "warning"
    )


def test_confirmed_notes_cannot_be_edited_or_confirmed_again(client: TestClient) -> None:
    login(client, "nurse")
    note = text_note(client, "Mrs. Anna Keller, pulse 80.")
    assert client.post(f"/notes/{note['id']}/confirm", json={}).status_code == 200
    assert client.post(f"/notes/{note['id']}/confirm", json={}).status_code == 409
    payload = {"payload": note["draft"]["payload"]}
    assert client.patch(f"/notes/{note['id']}/draft", json=payload).status_code == 409
    assert client.post(f"/notes/{note['id']}/reject", json={}).status_code == 409


def test_reject_is_audited_and_writes_nothing(client: TestClient, db: Session) -> None:
    login(client, "nurse")
    note = text_note(client, "Mrs. Anna Keller, pulse 80.")
    response = client.post(f"/notes/{note['id']}/reject", json={"reason": "wrong patient"})
    assert response.json()["status"] == "rejected"
    assert db.scalars(select(ConfirmedObservation)).all() == []
    event = db.scalar(select(AuditEvent).where(AuditEvent.action == "note.reject"))
    assert event is not None
    assert event.after == {"reason": "wrong patient"}


def test_patient_from_another_ward_cannot_be_selected(client: TestClient) -> None:
    login(client, "nurse")
    note = text_note(client, "Mrs. Keller, pulse 80.")
    other = PATIENTS["Peter Braun"]
    response = client.post(f"/notes/{note['id']}/confirm", json={"patient_id": str(other.id)})
    assert response.status_code == 403


def test_other_nurses_and_auditors_cannot_confirm(client: TestClient) -> None:
    login(client, "nurse")
    note = text_note(client, "Mrs. Anna Keller, pulse 80.")
    assert login(client, "nurse_b").post(f"/notes/{note['id']}/confirm", json={}).status_code == 403
    assert login(client, "auditor").post(f"/notes/{note['id']}/confirm", json={}).status_code == 403
    assert login(client, "charge").post(f"/notes/{note['id']}/confirm", json={}).status_code == 200


def test_implausible_value_entered_by_nurse_goes_to_uncertain(client: TestClient) -> None:
    login(client, "nurse")
    note = text_note(client, "Mrs. Anna Keller, pulse 80.")
    payload = note["draft"]["payload"]
    payload["vitals"] = [{"kind": "heart_rate", "value": 800, "unit": "/min", "source_text": "x"}]
    edited = client.patch(f"/notes/{note['id']}/draft", json={"payload": payload}).json()
    assert edited["draft"]["payload"]["vitals"] == []
    assert any("Implausible" in u for u in edited["draft"]["payload"]["uncertain"])


def test_draft_shows_review_hints_until_the_nurse_changes_the_field(client: TestClient) -> None:
    login(client, "nurse")
    text = "Mr. John Smith, pulse 72, BP 140 over 85, sorry, correction, 145 over 85."
    note = text_note(client, text)
    hints = note["draft"]["hints"]
    assert [(h["kind"], h["reason"], h["retracted_value"]) for h in hints] == [
        ("systolic_bp", "self_correction", 140)
    ]
    # The nurse decides it was 140 after all: the hint has done its job and disappears.
    payload = note["draft"]["payload"]
    for vital in payload["vitals"]:
        if vital["kind"] == "systolic_bp":
            vital["value"] = 140
    edited = client.patch(f"/notes/{note['id']}/draft", json={"payload": payload}).json()
    assert edited["draft"]["hints"] == []


def test_nurse_edits_are_stored_without_names(client: TestClient, db: Session) -> None:
    """The browser sees real names; every stored version and the audit log keep placeholders."""
    login(client, "nurse")
    note = text_note(client, "Mrs. Anna Keller, pulse 80. Anna says she feels fine.")
    payload = note["draft"]["payload"]
    assert "Anna" in payload["free_text_summary"] or "Anna" in payload["patient_mention"]
    payload["free_text_summary"] = "Anna Keller feels fine; rechecked Anna Keller at 14:00."
    edited = client.patch(f"/notes/{note['id']}/draft", json={"payload": payload})
    assert edited.status_code == 200, edited.text
    # Re-identified on the way out again.
    assert "Anna Keller" in edited.json()["draft"]["payload"]["free_text_summary"]

    stored = db.scalars(select(Extraction).where(Extraction.note_id == uuid.UUID(note["id"]))).all()
    assert [e.version for e in stored] == [1, 2]
    for extraction in stored:
        assert "Keller" not in json.dumps(extraction.payload)
        assert "Anna" not in json.dumps(extraction.payload)
    edit = db.scalar(select(AuditEvent).where(AuditEvent.action == "note.draft_edit"))
    assert edit is not None
    assert "Keller" not in json.dumps(edit.before) + json.dumps(edit.after)
    assert "<PATIENT_1>" in json.dumps(edit.after)


def test_list_limit_and_draft_size_are_validated(client: TestClient) -> None:
    login(client, "nurse")
    assert client.get("/notes?limit=0").status_code == 422
    assert client.get("/notes?limit=-1").status_code == 422
    assert client.get("/notes?limit=201").status_code == 422
    note = text_note(client, "Mrs. Anna Keller, pulse 80.")
    payload = note["draft"]["payload"]
    payload["symptoms"] = ["headache"] * 51
    assert client.patch(f"/notes/{note['id']}/draft", json={"payload": payload}).status_code == 422
    payload["symptoms"] = ["x" * 2001]
    assert client.patch(f"/notes/{note['id']}/draft", json={"payload": payload}).status_code == 422


def test_a_recording_can_be_transcribed_before_it_is_sent(client: TestClient, db: Session) -> None:
    """The nurse reads and fixes the text first; nothing is stored until she sends the note."""
    login(client, "nurse")
    data = (FIXTURES / "note.wav").read_bytes()
    response = client.post("/notes/transcribe", files={"audio": ("n.wav", data, "audio/wav")})
    assert response.status_code == 200
    body = response.json()
    assert "Anna Keller" in body["text"]
    assert body["model"] == "fake-transcriber"
    assert client.get("/notes").json() == []
    assert db.scalars(select(AuditEvent).where(AuditEvent.entity == "note")).all() == []
    bad = client.post("/notes/transcribe", files={"audio": ("x.wav", b"nope", "audio/wav")})
    assert bad.status_code == 422
    assert bad.json()["code"] == "payload_rejected"
    assert (
        login(client, "auditor")
        .post("/notes/transcribe", files={"audio": ("n.wav", data, "audio/wav")})
        .status_code
        == 403
    )
