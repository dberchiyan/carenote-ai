from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from carenote.auth.models import User
from carenote.contracts.extraction import Extraction
from carenote.demo_history import reset_notes, seed_history
from carenote.notes.models import ConfirmedObservation, NoteStatus, VoiceNote
from carenote.pipeline.review_hints import review_hints

NOW = datetime(2026, 11, 11, 14, 10, tzinfo=UTC)
# Two days of history exercise every rule; the full week is only slower (see seed_history).
DAYS = 2


def _seed(db: Session) -> list[VoiceNote]:
    reset_notes(db)
    seed_history(db, now=NOW, days=DAYS)
    return list(db.scalars(select(VoiceNote)))


def test_history_is_spread_over_days_and_never_in_the_future(db: Session) -> None:
    notes = _seed(db)
    days = {n.created_at.date() for n in notes}
    assert len(days) == DAYS + 1
    assert all(n.created_at < NOW for n in notes)
    # Realistic times, not one burst: many distinct minutes per day.
    assert len({n.created_at.replace(second=0) for n in notes}) > len(notes) * 0.8


def test_one_nurse_documents_a_plausible_number_of_notes_today(db: Session) -> None:
    notes = _seed(db)
    nurse = db.scalars(select(User).where(User.username == "nurse")).one()
    today = [n for n in notes if n.author_id == nurse.id and n.created_at.date() == NOW.date()]
    assert 3 <= len(today) <= 25


def test_only_confirmed_notes_have_observations_and_some_drafts_stay_open(db: Session) -> None:
    notes = _seed(db)
    by_status = {s: [n for n in notes if n.status is s] for s in NoteStatus}
    assert by_status[NoteStatus.IN_REVIEW], "today's latest round should await review"
    assert all(n.created_at.date() == NOW.date() for n in by_status[NoteStatus.IN_REVIEW])
    observed = set(db.scalars(select(ConfirmedObservation.note_id).distinct()))
    assert observed == {n.id for n in by_status[NoteStatus.CONFIRMED]}
    flags = set(db.scalars(select(ConfirmedObservation.flag).distinct()))
    assert {"normal", "warning"} <= flags


def test_drafts_stay_open_even_when_seeded_late_in_the_day(db: Session) -> None:
    reset_notes(db)
    seed_history(db, now=NOW.replace(hour=23), days=DAYS)
    open_drafts = db.scalars(select(VoiceNote).where(VoiceNote.status == NoteStatus.IN_REVIEW))
    assert len(list(open_drafts)) == 5


def test_history_is_deterministic(db: Session) -> None:
    first = len(_seed(db))
    second = len(_seed(db))
    assert first == second
    assert db.scalar(select(func.count()).select_from(VoiceNote)) == first


def test_nurse_edits_fix_genuine_extractor_misses(db: Session) -> None:
    notes = _seed(db)
    confirmed = [n for n in notes if n.status is NoteStatus.CONFIRMED]
    edited = [n for n in confirmed if n.latest_extraction and n.latest_extraction.source == "nurse"]
    assert 0.05 < len(edited) / len(confirmed) < 0.3
    for note in edited:
        ai, final = note.extractions[0].payload, note.extractions[-1].payload
        assert ai["vitals"] != final["vitals"]


def test_an_open_draft_shows_a_self_correction_hint(db: Session) -> None:
    notes = _seed(db)
    hints = [
        h
        for n in notes
        if n.status is NoteStatus.IN_REVIEW
        for h in review_hints(
            Extraction.model_validate(n.extractions[0].payload), n.redacted_transcript or ""
        )
    ]
    assert any(h.reason == "self_correction" for h in hints)
