import json
import re
from pathlib import Path

from evals.holdout import OUT, SPECS, build

from carenote.clinical.vocabulary import MEDICATIONS, SYMPTOMS
from carenote.patients.synthetic import generate_patients


def test_committed_holdout_file_matches_its_source() -> None:
    rows = [json.loads(line) for line in OUT.read_text().splitlines()]
    assert rows == build(), "run `make dataset` after editing evals/holdout.py"


def test_holdout_cases_are_well_formed() -> None:
    patients = {str(p.id): p for p in generate_patients()}
    rows = build()
    assert len(rows) == len(SPECS) >= 40
    for row in rows:
        if row["expected_patient_id"]:
            assert patients[row["expected_patient_id"]].ward == row["ward"]
            assert row["expected_patient_id"] in row["expected_patient_candidates"]
        assert set(row["expected_symptoms"]) <= SYMPTOMS.keys()
        assert {m["name"] for m in row["expected_medications"]} <= MEDICATIONS.keys()
        assert not {v["kind"] for v in row["expected_vitals"]} & set(
            row["expected_uncertain_kinds"]
        )


RECORD_PAGE = Path(__file__).parents[2] / "web/src/features/notes/components/new-note-page.tsx"


def test_the_record_screen_examples_are_in_the_holdout_set() -> None:
    """A client clicking an example sees exactly what the eval measured."""
    source = RECORD_PAGE.read_text()
    block = source[source.index("const EXAMPLES") : source.index("const STEPS")]
    examples = re.findall(r'^\s+text: "(.+)",$', block, re.MULTILINE)
    demo = {r["text"] for r in build() if "demo_example" in r["tags"]}
    assert len(examples) == 3
    assert set(examples) == demo
