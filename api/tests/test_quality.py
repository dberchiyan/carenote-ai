import json
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from carenote.audit.models import AuditEvent
from carenote.contracts.extraction import Extraction, Medication, Vital
from carenote.quality.corrections import diff_extractions
from tests.conftest import login


def _extraction(
    vitals: dict[str, float], symptoms: list[str], meds: list[Medication]
) -> Extraction:
    return Extraction(
        patient_mention=None,
        vitals=[Vital(kind=k, value=v, unit="x", source_text="") for k, v in vitals.items()],  # type: ignore[arg-type]
        symptoms=symptoms,
        medications=meds,
        free_text_summary="",
        uncertain=[],
    )


def test_diff_lists_added_removed_and_changed_fields() -> None:
    para = Medication(name="paracetamol", dose="500 mg", route="oral", source_text="")
    ai = _extraction({"heart_rate": 88, "temperature": 37.9}, ["headache"], [para])
    final = _extraction(
        {"heart_rate": 84, "systolic_bp": 132},
        ["headache", "nausea"],
        [para.model_copy(update={"dose": "1 g"})],
    )
    got = [(c.field, c.change, c.before, c.after) for c in diff_extractions(ai, final)]
    assert got == [
        ("heart_rate", "changed", "88", "84"),
        ("systolic_bp", "added", None, "132"),
        ("temperature", "removed", "37.9", None),
        ("symptom", "added", None, "nausea"),
        ("medication", "changed", "paracetamol 500 mg oral", "paracetamol 1 g oral"),
    ]
    assert diff_extractions(ai, ai) == []


def _confirmed_with_edit(client: TestClient, user: str, text: str) -> str:
    """The AI misses the colloquial BP ("BP's 132 on 78"); the nurse adds it, then confirms."""
    login(client, user)
    note_id: str = client.post("/notes/text", json={"text": text}).json()["id"]
    note: dict[str, Any] = client.get(f"/notes/{note_id}").json()
    payload = note["draft"]["payload"]
    payload["vitals"].append(
        {"kind": "systolic_bp", "value": 132, "unit": "mm[Hg]", "source_text": "BP's 132 on 78"}
    )
    assert client.patch(f"/notes/{note_id}/draft", json={"payload": payload}).status_code == 200
    assert client.post(f"/notes/{note_id}/confirm", json={}).status_code == 200
    return note_id


def test_corrections_show_what_nurses_changed_per_ward(client: TestClient) -> None:
    _confirmed_with_edit(client, "nurse", "Mrs. Anna Keller, pulse 80, BP's 132 on 78.")
    _confirmed_with_edit(client, "nurse_b", "Mr. Peter Braun, pulse 70, BP's 132 on 78.")
    login(client, "nurse")
    plain = client.post("/notes/text", json={"text": "Mrs. Anna Keller, pulse 81."}).json()["id"]
    client.post(f"/notes/{plain}/confirm", json={})

    body = login(client, "charge").get("/quality/corrections").json()
    assert body["ward"] == "3A"
    assert (body["confirmed_notes"], body["edited_notes"], body["edit_rate"]) == (2, 1, 0.5)
    assert body["by_field"] == [
        {"field": "systolic_bp", "added": 1, "removed": 0, "changed": 0, "total": 1}
    ]
    recent = body["recent"][0]
    assert "Keller" not in recent["redacted_transcript"]
    assert recent["changes"][0]["after"] == "132"

    assert login(client, "auditor").get("/quality/corrections").json()["edited_notes"] == 2


def test_export_turns_corrections_into_redacted_eval_cases(client: TestClient, db: Session) -> None:
    _confirmed_with_edit(client, "nurse", "Mrs. Anna Keller, pulse 80, BP's 132 on 78.")
    response = login(client, "charge").get("/quality/corrections/export")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/x-ndjson")
    assert "attachment" in response.headers["content-disposition"]
    cases = [json.loads(line) for line in response.text.splitlines()]
    assert len(cases) == 1
    case = cases[0]
    assert "Keller" not in case["text"]
    assert "<PATIENT_1>" in case["text"]
    assert {"kind": "systolic_bp", "value": 132.0, "unit": "mm[Hg]"} in case["expected_vitals"]
    assert "corrected_systolic_bp" in case["tags"]
    event = db.scalars(
        select(AuditEvent).where(AuditEvent.action == "quality.corrections_export")
    ).one()
    assert event.after == {"cases": 1, "days": 30, "ward": "3A"}


def test_eval_reports_list_the_latest_run_per_dataset(client: TestClient) -> None:
    runs = login(client, "auditor").get("/quality/evals").json()
    datasets = {r["dataset"] for r in runs if r["provider"] == "fake"}
    assert {"cases", "cases_holdout"} <= datasets
    holdout = next(r for r in runs if r["dataset"] == "cases_holdout")
    assert holdout["summary"]["cases"] == 40
    missed = [c for c in holdout["cases"] if not c["perfect"]]
    assert missed
    assert all(c["text"] and c["diffs"] for c in missed)


def test_quality_pages_are_for_charge_nurses_and_auditors(client: TestClient) -> None:
    login(client, "nurse")
    for path in ("/quality/evals", "/quality/corrections", "/quality/corrections/export"):
        assert client.get(path).status_code == 403
    client.cookies.clear()
    assert client.get("/quality/evals").status_code == 401
