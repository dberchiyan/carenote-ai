import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from carenote.audit.models import AuditEvent
from carenote.auth.session import COOKIE_NAME
from tests.conftest import login


def test_demo_users_lists_three_login_cards(client: TestClient) -> None:
    response = client.get("/auth/demo-users")
    assert response.status_code == 200
    assert [u["role"] for u in response.json()] == ["nurse", "charge_nurse", "auditor"]


def test_login_sets_httponly_cookie_and_me_works(client: TestClient) -> None:
    response = client.post("/auth/demo-login", json={"username": "nurse"})
    assert response.status_code == 200
    assert "httponly" in response.headers["set-cookie"].lower()
    me = client.get("/auth/me")
    assert me.status_code == 200
    assert me.json()["username"] == "nurse"
    assert me.json()["ward"] == "3A"


def test_login_is_audited(client: TestClient, db: Session) -> None:
    user = login(client, "charge").get("/auth/me").json()
    events = db.scalars(select(AuditEvent).where(AuditEvent.action == "auth.login")).all()
    assert any(str(e.actor_id) == user["id"] for e in events)


def test_unknown_user_cannot_log_in(client: TestClient) -> None:
    assert client.post("/auth/demo-login", json={"username": "mallory"}).status_code == 401


# The only routes a visitor without a session may call. Everything else must answer 401.
PUBLIC_ROUTES = {
    ("GET", "/health/live"),
    ("GET", "/health/ready"),
    ("GET", "/auth/demo-users"),
    ("POST", "/auth/demo-login"),
}


def test_every_route_denies_anonymous_callers_unless_listed_public(client: TestClient) -> None:
    """Deny by default, checked against the published OpenAPI paths so a new endpoint cannot
    forget: a route is either on the allow-list or it answers 401 without a session."""
    seen: set[tuple[str, str]] = set()
    paths: dict[str, dict[str, object]] = client.app.openapi()["paths"]  # type: ignore[attr-defined]
    for path, operations in paths.items():
        for method in operations:
            seen.add((method.upper(), path))
            if (method.upper(), path) in PUBLIC_ROUTES:
                continue
            url = path.replace("{note_id}", str(uuid.uuid4())).replace(
                "{patient_id}", str(uuid.uuid4())
            )
            response = client.request(method.upper(), url)
            assert response.status_code == 401, f"{method} {path} -> {response.status_code}"
    assert seen >= PUBLIC_ROUTES, "a public route disappeared; update the allow-list"
    assert len(seen) > 20


def test_login_username_is_bounded(client: TestClient) -> None:
    assert client.post("/auth/demo-login", json={"username": "x" * 65}).status_code == 422
    assert client.post("/auth/demo-login", json={"username": ""}).status_code == 422


def test_tampered_cookie_is_rejected(client: TestClient) -> None:
    login(client, "nurse")
    token = client.cookies[COOKIE_NAME]
    client.cookies.clear()
    client.cookies.set(COOKIE_NAME, token[:-2] + "xx")
    assert client.get("/auth/me").status_code == 401


def test_logout_clears_session(client: TestClient) -> None:
    login(client, "nurse")
    assert client.post("/auth/logout").status_code == 204
    assert client.get("/auth/me").status_code == 401
