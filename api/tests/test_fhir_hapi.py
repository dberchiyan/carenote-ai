"""Integration: exported bundles must validate against a real HAPI FHIR R4 server.

Run with `make test-integration` (needs `docker compose up fhir`).
"""

import os
from typing import Any

import httpx2 as httpx
import pytest

from carenote.alerts.rules import default_rules
from carenote.fhir.mapping import transaction_bundle
from tests.fhir_helpers import ANNA, sample_observations

FHIR = os.environ.get("CARENOTE_FHIR_BASE_URL", "http://localhost:8090/fhir")
pytestmark = pytest.mark.integration


def _bundle() -> dict[str, Any]:
    observations = sample_observations()
    performers = {o.note_id: "Nora Lindqvist (registered nurse)" for o in observations}
    return transaction_bundle(ANNA, observations, default_rules(), performers)


def _errors(outcome: dict[str, Any]) -> list[str]:
    return [
        f"{i.get('severity')}: {i.get('diagnostics')} @ {i.get('expression') or i.get('location')}"
        for i in outcome.get("issue", [])
        if i.get("severity") in ("error", "fatal")
    ]


def test_bundle_validates_with_zero_errors() -> None:
    bundle = _bundle()
    response = httpx.post(
        f"{FHIR}/Bundle/$validate",
        json=bundle,
        headers={"Content-Type": "application/fhir+json"},
        timeout=60,
    )
    outcome = response.json()
    assert outcome["resourceType"] == "OperationOutcome"
    assert _errors(outcome) == []


def test_each_resource_validates_with_zero_errors() -> None:
    bundle = _bundle()
    for entry in bundle["entry"]:
        resource = entry["resource"]
        response = httpx.post(
            f"{FHIR}/{resource['resourceType']}/$validate",
            json=resource,
            headers={"Content-Type": "application/fhir+json"},
            timeout=60,
        )
        assert _errors(response.json()) == [], resource["resourceType"]


def test_server_accepts_the_transaction() -> None:
    bundle = _bundle()
    response = httpx.post(
        FHIR, json=bundle, headers={"Content-Type": "application/fhir+json"}, timeout=60
    )
    assert response.status_code == 200, response.text
    statuses = [e["response"]["status"] for e in response.json()["entry"]]
    assert all(s.startswith(("200", "201")) for s in statuses)


def test_only_expected_warnings_remain() -> None:
    """The test server has no LOINC terminology loaded; everything else should be clean."""
    response = httpx.post(
        f"{FHIR}/Bundle/$validate",
        json=_bundle(),
        headers={"Content-Type": "application/fhir+json"},
        timeout=60,
    )
    warnings = [
        i.get("diagnostics", "") for i in response.json()["issue"] if i.get("severity") == "warning"
    ]
    assert all("http://loinc.org" in w for w in warnings), warnings
