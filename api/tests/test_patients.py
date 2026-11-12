from fastapi.testclient import TestClient

from carenote.patients.synthetic import generate_patients
from tests.conftest import login

WARD_A = [p for p in generate_patients() if p.ward == "3A"]
WARD_B = [p for p in generate_patients() if p.ward == "3B"]


def test_nurse_sees_own_ward_by_default(client: TestClient) -> None:
    response = login(client, "nurse").get("/patients")
    assert response.status_code == 200
    assert {p["id"] for p in response.json()} == {str(p.id) for p in WARD_A}


def test_nurse_of_ward_a_cannot_list_ward_b(client: TestClient) -> None:
    assert login(client, "nurse").get("/patients", params={"ward": "3B"}).status_code == 403


def test_nurse_of_ward_a_cannot_read_ward_b_patient(client: TestClient) -> None:
    response = login(client, "nurse").get(f"/patients/{WARD_B[0].id}")
    assert response.status_code == 403


def test_nurse_of_ward_b_sees_only_ward_b(client: TestClient) -> None:
    response = login(client, "nurse_b").get("/patients")
    assert {p["ward"] for p in response.json()} == {"3B"}
    assert login(client, "nurse_b").get(f"/patients/{WARD_A[0].id}").status_code == 403


def test_charge_nurse_is_limited_to_own_ward(client: TestClient) -> None:
    login(client, "charge")
    assert client.get("/patients").status_code == 200
    assert client.get("/patients", params={"ward": "3B"}).status_code == 403


def test_auditor_reads_all_wards(client: TestClient) -> None:
    login(client, "auditor")
    assert len(client.get("/patients").json()) == 30
    assert client.get("/patients", params={"ward": "3B"}).status_code == 200


def test_unknown_patient_is_404(client: TestClient) -> None:
    response = login(client, "nurse").get("/patients/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


def test_synthetic_patients_are_deterministic() -> None:
    assert generate_patients(seed=7) == generate_patients(seed=7)
    assert generate_patients(seed=7) != generate_patients(seed=8)
    assert len({p.id for p in generate_patients()}) == 30


def test_observations_are_a_bounded_window_with_a_total(client: TestClient) -> None:
    login(client, "nurse")
    note = client.post(
        "/notes/text", json={"text": "Mrs. Anna Keller, BP 120/80, pulse 70."}
    ).json()
    confirmed = client.post(f"/notes/{note['id']}/confirm", json={}).json()
    url = f"/patients/{confirmed['patient_id']}/observations"
    first = client.get(url, params={"limit": 2}).json()
    assert first["total"] == 3
    assert [o["kind"] for o in first["items"]] == ["diastolic_bp", "heart_rate"]
    rest = client.get(url, params={"limit": 2, "offset": 2}).json()
    assert [o["kind"] for o in rest["items"]] == ["systolic_bp"]
    assert client.get(url, params={"days": 0}).status_code == 422
    assert client.get(url, params={"days": 366}).status_code == 422
