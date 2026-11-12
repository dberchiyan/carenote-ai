"""Shift handover: confirmed data only, flagged patients first, rooms (not names) to any writer."""

import datetime as dt
import uuid
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from carenote.audit.models import AuditEvent
from carenote.contracts.handover import HandoverFacts, HandoverText, RoomSummary
from carenote.db import utcnow
from carenote.handover.routes import get_handover_writer
from carenote.notes.models import ConfirmedObservation
from carenote.patients.synthetic import generate_patients
from tests.conftest import login

PATIENTS = {p.full_name: p for p in generate_patients()}
ANNA, SMITH = PATIENTS["Anna Keller"], PATIENTS["John Smith"]


def confirm(client: TestClient, text: str) -> dict[str, Any]:
    note = client.post("/notes/text", json={"text": text}).json()
    confirmed: dict[str, Any] = client.post(f"/notes/{note['id']}/confirm", json={}).json()
    assert confirmed["status"] == "confirmed", confirmed
    return confirmed


def test_only_ward_clinicians_get_a_handover(client: TestClient) -> None:
    assert client.get("/handover").status_code == 401
    assert login(client, "auditor").get("/handover").status_code == 403
    assert login(client, "nurse").get("/handover").status_code == 200
    assert login(client, "nurse").get("/handover", params={"hours": 2}).status_code == 422


def test_flagged_patients_come_first_with_what_changed_since_the_last_shift(
    client: TestClient, db: Session
) -> None:
    # Before this shift Anna's sats were normal.
    db.add(
        ConfirmedObservation(
            id=uuid.uuid4(), note_id=_any_note(client, db), patient_id=ANNA.id, kind="spo2",
            code="59408-5", value=96, unit="%", flag="normal",
            effective_at=utcnow() - dt.timedelta(hours=20),
        )
    )  # fmt: skip
    db.commit()
    login(client, "nurse")
    dictation = "Mrs. Anna Keller, sats 88 percent, complains of a headache"
    confirm(client, f"{dictation}, gave 500 mg paracetamol orally.")
    confirm(client, "Mr. John Smith, pulse 72, temperature 36.8.")

    h = client.get("/handover", params={"hours": 12}).json()
    assert h["ward"] == "3A"
    first = h["patients"][0]
    assert first["room"] == ANNA.room
    assert first["priority"] == "critical"
    spo2 = next(v for v in first["vitals"] if v["kind"] == "spo2")
    assert (spo2["value"], spo2["previous"], spo2["change"]) == (88, 96, "new_flag")
    assert "headache" in first["symptoms"]
    assert first["medications"][0]["name"] == "paracetamol"
    assert "SpO₂ 88% (critical, new, was 96)" in first["summary"]
    assert "Given paracetamol" in first["summary"]
    smith = next(p for p in h["patients"] if p["room"] == SMITH.room)
    assert smith["priority"] == "stable"
    assert smith["summary"].startswith("Stable:")
    assert h["counts"]["critical"] >= 1
    assert h["written_by"] == "rules"
    assert "critical" in h["summary"]


def test_a_reading_before_the_window_is_the_previous_value_not_the_current(
    client: TestClient, db: Session
) -> None:
    login(client, "nurse")
    note_id = _any_note(client, db)
    db.add(
        ConfirmedObservation(
            id=uuid.uuid4(), note_id=note_id, patient_id=SMITH.id, kind="heart_rate",
            code="8867-4", value=130, unit="/min", flag="warning",
            effective_at=utcnow() - dt.timedelta(hours=30),
        )
    )  # fmt: skip
    db.commit()
    smith = next(p for p in client.get("/handover").json()["patients"] if p["room"] == SMITH.room)
    assert all(v["kind"] != "heart_rate" or v["value"] != 130 for v in smith["vitals"])


def test_the_writer_sees_rooms_not_names_and_viewing_is_audited(
    client: TestClient, db: Session
) -> None:
    seen: list[HandoverFacts] = []

    class SpyWriter:
        name = "spy"

        def write(self, facts: HandoverFacts) -> tuple[HandoverText, str]:
            seen.append(facts)
            return (
                HandoverText(
                    ward_summary="ok",
                    patients=[
                        RoomSummary(room=p.room, summary=f"room {p.room}") for p in facts.patients
                    ],
                ),
                "spy-model",
            )

    client.app.dependency_overrides[get_handover_writer] = SpyWriter  # type: ignore[attr-defined]
    login(client, "nurse")
    confirm(client, "Mrs. Anna Keller, pulse 80.")
    h = client.get("/handover").json()
    assert h["written_by"] == "spy-model"
    assert h["patients"][0]["summary"].startswith("room ")
    dumped = seen[0].model_dump_json()
    for p in generate_patients():
        assert p.family_name not in dumped
        assert p.given_name not in dumped
    event = db.scalars(select(AuditEvent).where(AuditEvent.action == "handover.view")).one()
    assert event.after is not None
    assert event.after["written_by"] == "spy-model"


def _any_note(client: TestClient, db: Session) -> uuid.UUID:
    """Observations need a note to belong to; any note on the ward will do for a fixture row."""
    login(client, "nurse")
    note = client.post("/notes/text", json={"text": "Mrs. Anna Keller, pulse 70."}).json()
    return uuid.UUID(note["id"])


def test_the_claude_writer_falls_back_to_rules_when_the_answer_is_unusable() -> None:
    from types import SimpleNamespace

    import anthropic
    import httpx

    from carenote.contracts.handover import PatientFacts
    from carenote.pipeline.prompts import load_prompt
    from carenote.providers.anthropic_handover import AnthropicHandoverWriter

    facts = HandoverFacts(
        ward="3A",
        hours=12,
        unassigned_drafts=0,
        patients=[
            PatientFacts(room="301a", priority="stable", vitals=[], symptoms=[], medications=[],
                         notes_confirmed=0, open_drafts=0),
        ],
    )  # fmt: skip

    def writer(answer: Any) -> AnthropicHandoverWriter:
        def parse(**kwargs: Any) -> Any:
            assert "Keller" not in kwargs["messages"][0]["content"]
            if isinstance(answer, Exception):
                raise answer
            return answer

        client = SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(parse=parse)))
        return AnthropicHandoverWriter("key", load_prompt("handover_v1"), client=client)  # type: ignore[arg-type]

    usage = SimpleNamespace(input_tokens=900, output_tokens=120)
    good = HandoverText(
        ward_summary="1 patient.", patients=[RoomSummary(room="301a", summary="ok")]
    )
    text, by = writer(
        SimpleNamespace(parsed_output=good, model="claude-sonnet-5-5", usage=usage)
    ).write(facts)
    assert (text.patients[0].summary, by) == ("ok", "claude-sonnet-5-5")

    wrong_rooms = good.model_copy(update={"patients": [RoomSummary(room="999", summary="?")]})
    _, by = writer(SimpleNamespace(parsed_output=wrong_rooms, model="m", usage=usage)).write(facts)
    assert by == "rules"

    down = anthropic.APIConnectionError(request=httpx.Request("POST", "https://api.anthropic.com"))  # type: ignore[arg-type]
    text, by = writer(down).write(facts)
    assert by == "rules"
    assert text.patients[0].summary == "No confirmed observations this shift."
