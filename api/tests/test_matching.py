from carenote.patients.matching import match_patient
from carenote.patients.synthetic import generate_patients

WARD_A = [p for p in generate_patients() if p.ward == "3A"]
BY_NAME = {p.full_name: p for p in WARD_A}
ANNA, HANNA, SMITH = BY_NAME["Anna Keller"], BY_NAME["Hanna Keller"], BY_NAME["John Smith"]


def test_full_name_is_matched() -> None:
    result = match_patient("Mrs. Anna Keller, BP 150 over 90.", WARD_A)
    assert result.status == "matched"
    assert result.selected_id == ANNA.id


def test_near_identical_name_on_the_same_words_loses() -> None:
    result = match_patient("Hanna Keller, pulse 80.", WARD_A)
    assert result.selected_id == HANNA.id
    assert ANNA.id in {c.patient_id for c in result.candidates}


def test_title_and_shared_family_name_is_ambiguous() -> None:
    result = match_patient("Mrs. Keller, temperature 38.", WARD_A)
    assert result.status == "ambiguous"
    assert result.selected_id is None
    assert {ANNA.id, HANNA.id} <= {c.patient_id for c in result.candidates}


def test_room_number_disambiguates() -> None:
    result = match_patient(f"Mrs. Keller in {HANNA.room}, temperature 38.", WARD_A)
    assert result.selected_id == HANNA.id


def test_two_patients_in_one_note_need_a_human() -> None:
    result = match_patient("Anna Keller BP 120/80. Also saw Mr. Smith, asleep.", WARD_A)
    assert result.status == "ambiguous"
    assert {ANNA.id, SMITH.id} <= {c.patient_id for c in result.candidates}


def test_single_transcription_typo_still_matches() -> None:
    assert match_patient("Mrs. Ana Keller, pulse 72.", WARD_A).selected_id == ANNA.id


def test_badly_garbled_name_is_offered_as_a_candidate_not_selected() -> None:
    result = match_patient("Mrs. Ana Kellar, pulse 72.", WARD_A)
    assert result.selected_id is None
    assert ANNA.id in {c.patient_id for c in result.candidates}


def test_no_patient_mentioned() -> None:
    result = match_patient("Blood pressure 120 over 80, pulse 72.", WARD_A)
    assert result.status == "none"
    assert result.selected_id is None


def test_patient_of_another_ward_is_not_a_candidate() -> None:
    assert match_patient("Mr. Peter Braun, pulse 72.", WARD_A).status == "none"


def test_a_first_name_alone_is_offered_but_never_auto_selected() -> None:
    """ "John, 38 temperature" names the only John on the ward: the nurse gets him as a
    candidate to confirm, not a silent match on a first name."""
    result = match_patient("John, 38 temperature, 88 pulse.", WARD_A)
    assert result.status == "none"
    assert result.selected_id is None
    assert [c.patient_id for c in result.candidates] == [SMITH.id]
    assert result.candidates[0].matched_text == "john"


def test_a_shared_first_name_lists_everyone_with_it() -> None:
    marias = [p for p in WARD_A if p.given_name == "Maria"]
    assert len(marias) >= 2
    result = match_patient("Maria, pulse 70.", WARD_A)
    assert result.selected_id is None
    assert {p.id for p in marias} <= {c.patient_id for c in result.candidates}


def test_a_family_name_alone_is_offered_like_a_first_name() -> None:
    """Whisper punctuates dictation: "Smith, 80, pulse, headache." still names the Smith."""
    result = match_patient("Smith, 80, pulse, headache.", WARD_A)
    assert result.selected_id is None
    assert [c.patient_id for c in result.candidates] == [SMITH.id]
    assert result.candidates[0].matched_text == "smith"
