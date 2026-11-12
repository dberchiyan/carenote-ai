"""Operational hardening: no API docs in prod, a login rate limit, logout in the audit log,
and audit viewing that does not flood its own log."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from carenote.audit.models import AuditEvent
from carenote.config import Settings
from carenote.main import create_app
from carenote.ratelimit import LOGIN_WINDOW, FixedWindow
from tests.conftest import login


def test_api_docs_are_off_in_prod(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "carenote.main.get_settings",
        lambda: Settings(env="prod", session_secret="x" * 32),  # type: ignore[arg-type]
    )
    prod = create_app()
    assert prod.docs_url is None
    assert prod.openapi_url is None
    monkeypatch.setattr("carenote.main.get_settings", lambda: Settings(env="dev"))
    assert create_app().docs_url == "/docs"


def test_fixed_window_counts_per_key_and_forgets_after_the_window() -> None:
    now = [0.0]
    window = FixedWindow(limit=2, window_s=60, clock=lambda: now[0])
    assert [window.allow("a") for _ in range(3)] == [True, True, False]
    assert window.allow("b")  # another client is not affected
    now[0] = 61
    assert window.allow("a")


def test_login_is_rate_limited_per_client(client: TestClient) -> None:
    LOGIN_WINDOW.reset()
    try:
        for _ in range(LOGIN_WINDOW.limit):
            assert client.post("/auth/demo-login", json={"username": "nurse"}).status_code == 200
        blocked = client.post("/auth/demo-login", json={"username": "nurse"})
        assert blocked.status_code == 429
        assert blocked.json()["code"] == "rate_limited"
        assert blocked.json()["details"]["retry_after_s"] == 60
        # The proxy forwards the browser's address: a different one gets its own budget.
        other = client.post(
            "/auth/demo-login", json={"username": "nurse"}, headers={"x-forwarded-for": "10.0.0.9"}
        )
        assert other.status_code == 200
    finally:
        LOGIN_WINDOW.reset()


def test_logout_is_audited(client: TestClient, db: Session) -> None:
    login(client, "nurse")
    assert client.post("/auth/logout").status_code == 204
    event = db.scalars(select(AuditEvent).where(AuditEvent.action == "auth.logout")).one()
    assert event.actor_id is not None


def test_repeated_identical_audit_views_are_recorded_once(client: TestClient, db: Session) -> None:
    login(client, "auditor")
    for _ in range(3):
        assert client.get("/audit", params={"action": "auth.login"}).status_code == 200
    assert client.get("/audit", params={"action": "note.confirm"}).status_code == 200
    views = db.scalar(
        select(func.count()).select_from(AuditEvent).where(AuditEvent.action == "audit.view")
    )
    assert views == 2  # one per distinct view, not one per poll
