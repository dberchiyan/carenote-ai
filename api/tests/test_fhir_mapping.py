from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from carenote.alerts.rules import default_rules
from carenote.audit.models import AuditEvent
from carenote.fhir.mapping import transaction_bundle
from tests.conftest import login
from tests.fhir_helpers import ANNA, sample_observations


def _bundle() -> dict[str, Any]:
    return transaction_bundle(ANNA, sample_observations(), default_rules())


def _observations(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        e["resource"] for e in bundle["entry"] if e["resource"]["resourceType"] == "Observation"
    ]


def _code(resource: dict[str, Any]) -> str:
    code: str = resource["code"]["coding"][0]["code"]
    return code


def test_transaction_bundle_has_patient_then_observations() -> None:
    bundle = _bundle()
    assert bundle["type"] == "transaction"
    patient = bundle["entry"][0]
    assert patient["request"] == {"method": "PUT", "url": f"Patient/{ANNA.id}"}
    assert patient["resource"]["identifier"][0]["value"] == ANNA.mrn
    assert patient["resource"]["name"][0] == {
        "use": "official",
        "family": "Keller",
        "given": ["Anna"],
    }
    for obs in _observations(bundle):
        assert obs["subject"]["reference"] == f"urn:uuid:{ANNA.id}"
        assert obs["status"] == "final"


def test_blood_pressure_is_one_panel_with_two_components() -> None:
    obs = _observations(_bundle())
    codes = sorted(_code(o) for o in obs)
    assert codes == sorted(
        ["85354-9", "8867-4", "8310-5", "59408-5", "9279-1", "29463-7", "2339-0"]
    )
    panel = next(o for o in obs if _code(o) == "85354-9")
    components = {c["code"]["coding"][0]["code"]: c for c in panel["component"]}
    assert components["8480-6"]["valueQuantity"] == {
        "value": 168, "unit": "mmHg", "system": "http://unitsofmeasure.org", "code": "mm[Hg]",
    }  # fmt: skip
    assert components["8462-4"]["valueQuantity"]["value"] == 96
    assert "valueQuantity" not in panel


def test_units_categories_and_interpretations() -> None:
    by_code = {_code(o): o for o in _observations(_bundle())}
    assert by_code["8310-5"]["valueQuantity"]["code"] == "Cel"
    assert by_code["8867-4"]["valueQuantity"]["code"] == "/min"
    assert by_code["2339-0"]["category"][0]["coding"][0]["code"] == "laboratory"
    assert by_code["8867-4"]["category"][0]["coding"][0]["code"] == "vital-signs"
    interp = {
        c: o["interpretation"][0]["coding"][0]["code"]
        for c, o in by_code.items()
        if "interpretation" in o
    }
    assert interp["8310-5"] == "H"  # 38.4 °C: warning, high
    assert interp["59408-5"] == "LL"  # SpO2 87 %: critical, low
    assert interp["2339-0"] == "L"  # glucose 62: warning, low
    assert interp["8867-4"] == "N"
    assert "29463-7" not in interp  # no rule for weight


def test_export_keeps_the_flag_confirmed_at_the_time() -> None:
    """Rules may tighten later; what the nurse confirmed is what the record says."""
    import uuid

    from carenote.fhir.mapping import observation_resources
    from tests.fhir_helpers import Obs

    then_warning = Obs("temperature", 38.4, uuid.uuid4(), flag="critical")
    [resource] = observation_resources([then_warning], "urn:uuid:x", default_rules())
    assert resource["interpretation"][0]["coding"][0]["code"] == "HH"
    assert "Critical high" in resource["text"]["div"]


def test_export_endpoint_returns_fhir_json_and_is_audited(client: TestClient, db: Session) -> None:
    login(client, "nurse")
    note = client.post(
        "/notes/text", json={"text": "Mrs. Anna Keller, BP 150/90, pulse 88."}
    ).json()
    assert client.post(f"/notes/{note['id']}/confirm", json={}).status_code == 200

    response = client.get(f"/patients/{ANNA.id}/fhir")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/fhir+json")
    assert "attachment" in response.headers["content-disposition"]
    bundle = response.json()
    assert [e["resource"]["resourceType"] for e in bundle["entry"]] == [
        "Patient",
        "Observation",
        "Observation",
    ]

    event = db.scalar(select(AuditEvent).where(AuditEvent.action == "fhir.export"))
    assert event is not None
    assert event.entity_id == str(ANNA.id)

    observations = client.get(f"/patients/{ANNA.id}/observations").json()["items"]
    assert {o["code"] for o in observations} == {"8480-6", "8462-4", "8867-4"}


def test_export_respects_ward_access(client: TestClient) -> None:
    assert login(client, "nurse_b").get(f"/patients/{ANNA.id}/fhir").status_code == 403
    assert login(client, "nurse_b").get(f"/patients/{ANNA.id}/observations").status_code == 403
