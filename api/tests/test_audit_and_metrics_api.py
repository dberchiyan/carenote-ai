from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from carenote.audit.models import AuditEvent
from carenote.config import Settings, get_settings
from carenote.contracts.llm import TranscriptionResult
from carenote.providers.factory import get_transcription
from tests.conftest import login

FIXTURES = Path(__file__).parent / "fixtures"

NOTE = "Mrs. Anna Keller, BP 150/90, pulse 88."


def test_only_auditors_read_the_audit_log(client: TestClient) -> None:
    for user in ("nurse", "charge", "nurse_b"):
        assert login(client, user).get("/audit").status_code == 403
    assert login(client, "auditor").get("/audit").status_code == 200


def test_audit_log_filters_and_audits_its_own_viewing(client: TestClient, db: Session) -> None:
    login(client, "nurse")
    note = client.post("/notes/text", json={"text": NOTE}).json()
    client.post(f"/notes/{note['id']}/confirm", json={})

    login(client, "auditor")
    filters = {"entity": "note", "entity_id": note["id"]}
    page = client.get("/audit", params=filters).json()
    events = page["items"]
    assert [e["action"] for e in events] == ["note.confirm", "note.create"]
    assert events[0]["actor_name"] == "Nora Lindqvist"
    assert (page["total"], page["limit"], page["offset"]) == (2, 100, 0)
    assert client.get("/audit", params={"action": "auth.login"}).json()["items"]

    views = db.scalars(select(AuditEvent).where(AuditEvent.action == "audit.view")).all()
    assert len(views) == 2


def test_llm_metrics_by_role(client: TestClient) -> None:
    login(client, "nurse")
    client.post("/notes/text", json={"text": NOTE})
    assert client.get("/metrics/llm").status_code == 403

    charge = login(client, "charge").get("/metrics/llm").json()
    assert charge["ward"] == "3A"
    assert charge["total_extractions"] == 1
    assert charge["daily"][0]["model"] == "rule-based-v1"
    assert charge["daily"][0]["input_tokens"] > 0

    login(client, "nurse_b")
    client.post("/notes/text", json={"text": "Mr. Peter Braun, pulse 70."})
    assert login(client, "charge").get("/metrics/llm").json()["total_extractions"] == 1
    assert login(client, "auditor").get("/metrics/llm").json()["total_extractions"] == 2


def test_alert_rules_are_readable_by_signed_in_users(client: TestClient) -> None:
    assert client.get("/alerts/rules").status_code == 401
    rules = login(client, "nurse").get("/alerts/rules").json()
    assert rules["rules"]["spo2"]["warning_below"] == 94


def test_audit_log_pages_are_stable_and_bounded(client: TestClient) -> None:
    login(client, "nurse")
    note = client.post("/notes/text", json={"text": NOTE}).json()
    client.post(f"/notes/{note['id']}/reject", json={})
    login(client, "auditor")
    filters = {"entity": "note", "entity_id": note["id"], "limit": 1}
    first = client.get("/audit", params=filters).json()
    second = client.get("/audit", params={**filters, "offset": 1}).json()
    assert first["total"] == second["total"] == 2
    assert [e["action"] for e in first["items"]] == ["note.reject"]
    assert [e["action"] for e in second["items"]] == ["note.create"]
    assert client.get("/audit", params={"limit": 501}).status_code == 422
    assert client.get("/audit", params={"offset": -1}).status_code == 422


class PricedTranscription:
    name = "priced"

    def transcribe(
        self, audio: bytes, filename: str, content_type: str, duration_s: float | None = None
    ) -> TranscriptionResult:
        return TranscriptionResult(
            text="Mrs. Anna Keller, pulse 72.", model="gpt-4o-transcribe", latency_ms=5,
            cost_usd=0.0123,
        )  # fmt: skip


def test_transcription_cost_is_kept_and_counted(client: TestClient, tmp_path: Path) -> None:
    overrides = client.app.dependency_overrides  # type: ignore[attr-defined]
    overrides[get_transcription] = PricedTranscription
    overrides[get_settings] = lambda: Settings(audio_dir=tmp_path)  # never write into the repo
    login(client, "nurse")
    data = (FIXTURES / "note.wav").read_bytes()
    note_id = client.post("/notes", files={"audio": ("n.wav", data, "audio/wav")}).json()["id"]
    assert client.get(f"/notes/{note_id}").json()["status"] == "in_review"

    metrics = login(client, "charge").get("/metrics/llm").json()
    assert metrics["transcription"] == {"notes": 1, "seconds": 4.8, "cost_usd": 0.0123}
    assert metrics["extraction_cost_usd"] == 0.0
    assert metrics["total_cost_usd"] == 0.0123
    assert metrics["avg_cost_per_note_usd"] == 0.0123


def test_audit_actions_come_from_the_log_itself(client: TestClient) -> None:
    login(client, "nurse")
    client.post("/notes/text", json={"text": NOTE})
    assert client.get("/audit/actions").status_code == 403
    actions = login(client, "auditor").get("/audit/actions").json()
    assert {"auth.login", "note.create"} <= set(actions)
    assert actions == sorted(actions)
