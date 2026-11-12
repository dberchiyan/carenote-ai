"""Request ids on every response, note ids on every processing log line, a deadline per note."""

import json
import logging
import uuid
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Connection, select
from sqlalchemy.orm import Session

from carenote.auth.models import User
from carenote.notes import processing
from carenote.notes.models import NoteStatus, VoiceNote
from carenote.observability import (
    REQUEST_ID_HEADER,
    ContextFilter,
    JsonFormatter,
    bound_note,
    clean_request_id,
    request_id_var,
)
from carenote.providers.fake import FakeTranscription, RuleBasedLLM
from tests.conftest import login


def test_every_response_carries_a_request_id(client: TestClient) -> None:
    generated = client.get("/health/live").headers[REQUEST_ID_HEADER]
    assert len(generated) == 16
    echoed = client.get("/health/live", headers={REQUEST_ID_HEADER: "trace-42"})
    assert echoed.headers[REQUEST_ID_HEADER] == "trace-42"
    # Errors too, including the ones FastAPI raises itself.
    assert REQUEST_ID_HEADER in client.get("/auth/me").headers
    assert REQUEST_ID_HEADER in client.get("/nope").headers


def test_a_hostile_request_id_is_replaced_not_echoed() -> None:
    assert clean_request_id("abc-123.DEF_x") == "abc-123.DEF_x"
    assert clean_request_id("<script>alert(1)</script>") == "scriptalert1script"
    assert clean_request_id("x" * 200) == "x" * 64
    assert clean_request_id("\r\nInjected: header") == "Injectedheader"
    assert clean_request_id("") is None
    assert clean_request_id("!!!") is None


def _record(message: str, **extra: Any) -> logging.LogRecord:
    record = logging.LogRecord("carenote.test", logging.INFO, __file__, 1, message, (), None)
    for key, value in extra.items():
        setattr(record, key, value)
    ContextFilter().filter(record)
    return record


def test_json_lines_carry_context_and_extra_fields() -> None:
    token = request_id_var.set("req-1")
    try:
        with bound_note(uuid.UUID(int=7)):
            record = _record("draft ready", step="extract", cost_usd=0.01)
            line = json.loads(JsonFormatter().format(record))
    finally:
        request_id_var.reset(token)
    assert line["msg"] == "draft ready"
    assert line["level"] == "INFO"
    assert line["request_id"] == "req-1"
    assert line["note_id"] == str(uuid.UUID(int=7))
    assert line["step"] == "extract"
    assert line["cost_usd"] == 0.01
    assert line["ts"].endswith("+00:00")


def test_processing_log_lines_are_stamped_with_the_note_id(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    login(client, "nurse")
    with caplog.at_level(logging.INFO, logger="carenote.notes.processing"):
        note_id = client.post("/notes/text", json={"text": "Mrs. Anna Keller, pulse 70."}).json()[
            "id"
        ]
    ready = [r for r in caplog.records if r.getMessage().startswith("draft ready")]
    assert ready, "processing should log the finished draft"
    record: Any = ready[0]
    assert record.note_id == note_id
    assert record.step == "extract"
    assert record.model == "rule-based-v1"
    assert record.outcome == "in_review"


def test_a_note_past_the_deadline_fails_retryably(connection: Connection, tmp_path: Path) -> None:
    """The worker gives up before the next step rather than holding the process; the nurse
    sees why and can retry."""

    def make_session() -> Session:
        return Session(
            bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False
        )

    db = make_session()
    nurse = db.scalars(select(User).where(User.username == "nurse")).one()
    note = VoiceNote(
        ward="3A", author_id=nurse.id, source="text", status=NoteStatus.TRANSCRIBED,
        transcript="Mrs. Anna Keller, pulse 70.",
    )  # fmt: skip
    db.add(note)
    db.commit()
    ticks = iter([0.0, 500.0])  # start, then the check before extraction: 500 s later

    processing.process_note(
        note.id,
        session_factory=make_session,
        llm=RuleBasedLLM(),
        transcription=FakeTranscription(),
        audio_dir=tmp_path,
        deadline_s=120,
        clock=lambda: next(ticks),
    )
    with make_session() as check:
        stored = check.get(VoiceNote, note.id)
        assert stored is not None
        assert stored.status is NoteStatus.TRANSCRIBED
        assert stored.error_step == "extract"
        assert stored.error_message is not None
        assert "longer than 120 s" in stored.error_message
        assert stored.latest_extraction is None
