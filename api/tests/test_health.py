from collections.abc import Iterator

from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from carenote.db import get_session
from carenote.main import create_app


def test_live(client: TestClient) -> None:
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_when_database_answers(client: TestClient) -> None:
    response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


def test_ready_when_database_is_down() -> None:
    class BrokenSession:
        def execute(self, *_: object) -> None:
            raise OperationalError("SELECT 1", {}, Exception("connection refused"))

    def session_override() -> Iterator[BrokenSession]:
        yield BrokenSession()

    app = create_app()
    app.dependency_overrides[get_session] = session_override
    with TestClient(app) as client:
        response = client.get("/health/ready")
    assert response.status_code == 503
    assert response.json() == {"status": "unavailable", "database": "unavailable"}
