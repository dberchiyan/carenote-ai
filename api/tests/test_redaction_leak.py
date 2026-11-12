"""Privacy guarantee: no patient name from the database ever reaches an LLM provider.

One test per dictation so the run spreads across xdist workers (120 notes through the API
is the slowest thing in the suite, especially over a remote database).
"""

import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from carenote.patients.synthetic import generate_patients
from carenote.providers.fake import RuleBasedLLM
from tests.conftest import login

CASES = [
    json.loads(line)
    for line in (Path(__file__).parents[1] / "evals/data/cases.jsonl").read_text().splitlines()
]
# The seeded patients are the synthetic ones, so their names are known without a query.
NAMES = {n for p in generate_patients() for n in (p.given_name, p.family_name)}
NURSE_FOR_WARD = {"3A": "nurse", "3B": "nurse_b"}


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_no_patient_name_appears_in_the_outgoing_llm_request(
    client: TestClient, llm: RuleBasedLLM, case: dict[str, str]
) -> None:
    assert len(NAMES) > 30
    login(client, NURSE_FOR_WARD[case["ward"]])
    assert client.post("/notes/text", json={"text": case["text"]}).status_code == 202
    assert len(llm.requests) == 1
    request = llm.requests[0]
    for name in NAMES:
        assert not re.search(rf"\b{re.escape(name)}\b", request, re.IGNORECASE), (
            f"{name!r} leaked to the LLM: {request[-300:]}"
        )
