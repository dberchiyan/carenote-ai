"""Every error answer has the same shape: `{code, message, details}`.

The web app branches on `code` (a closed enum published in OpenAPI), never on the message text.
"""

import uuid

import pytest
from fastapi.testclient import TestClient

from carenote.errors import ErrorCode
from tests.conftest import login


def _assert_error(body: dict[str, object], code: ErrorCode) -> None:
    assert set(body) == {"code", "message", "details"}, body
    assert body["code"] == code.value
    assert isinstance(body["message"], str)
    assert body["message"]
    assert isinstance(body["details"], dict)


def test_anonymous_request_is_unauthenticated(client: TestClient) -> None:
    response = client.get("/auth/me")
    assert response.status_code == 401
    _assert_error(response.json(), ErrorCode.UNAUTHENTICATED)


def test_wrong_role_is_forbidden(client: TestClient) -> None:
    response = login(client, "nurse").get("/audit")
    assert response.status_code == 403
    _assert_error(response.json(), ErrorCode.FORBIDDEN)


def test_missing_note_is_not_found(client: TestClient) -> None:
    response = login(client, "nurse").get(f"/notes/{uuid.uuid4()}")
    assert response.status_code == 404
    _assert_error(response.json(), ErrorCode.NOT_FOUND)


def test_unknown_path_is_not_found_in_the_same_shape(client: TestClient) -> None:
    response = client.get("/no-such-route")
    assert response.status_code == 404
    _assert_error(response.json(), ErrorCode.NOT_FOUND)


def test_invalid_body_lists_the_offending_fields(client: TestClient) -> None:
    response = client.post("/auth/demo-login", json={"username": ""})
    assert response.status_code == 422
    body = response.json()
    _assert_error(body, ErrorCode.VALIDATION_ERROR)
    assert body["details"]["fields"][0]["path"] == "body.username"
    assert "message" in body["details"]["fields"][0]


def test_invalid_query_is_a_validation_error(client: TestClient) -> None:
    response = login(client, "nurse").get("/notes", params={"limit": -1})
    assert response.status_code == 422
    _assert_error(response.json(), ErrorCode.VALIDATION_ERROR)


@pytest.mark.parametrize("step", ["confirm", "reject"])
def test_state_conflicts_carry_the_note_status(client: TestClient, step: str) -> None:
    login(client, "nurse")
    note_id = client.post("/notes/text", json={"text": "Hanna Keller, pulse 72."}).json()["id"]
    assert client.post(f"/notes/{note_id}/reject", json={}).status_code == 200
    response = client.post(f"/notes/{note_id}/{step}", json={})
    assert response.status_code == 409
    body = response.json()
    _assert_error(body, ErrorCode.INVALID_STATE)
    assert body["details"]["status"] == "rejected"


def test_error_schema_and_codes_are_published_in_openapi(client: TestClient) -> None:
    spec = client.app.openapi()  # type: ignore[attr-defined]
    schemas = spec["components"]["schemas"]
    assert set(schemas["ErrorOut"]["properties"]) == {"code", "message", "details"}
    assert set(schemas["ErrorCode"]["enum"]) == {c.value for c in ErrorCode}
    # Every operation documents the error shape so the generated client types it.
    for path, operations in spec["paths"].items():
        for method, op in operations.items():
            ref = op["responses"]["default"]["content"]["application/json"]["schema"]["$ref"]
            assert ref.endswith("/ErrorOut"), f"{method} {path}"
