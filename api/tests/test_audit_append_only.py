import pytest
from sqlalchemy import Engine, text
from sqlalchemy.exc import DBAPIError, ProgrammingError
from sqlalchemy.orm import Session

from carenote.audit import service as audit


def _insert_event(engine: Engine) -> str:
    with Session(engine) as session:
        event = audit.record(session, actor_id=None, action="test.event", entity="test")
        session.commit()
        return str(event.id)


def test_app_role_can_insert_and_read(app_engine: Engine) -> None:
    event_id = _insert_event(app_engine)
    with app_engine.connect() as conn:
        found = conn.scalar(
            text("SELECT count(*) FROM audit_events WHERE id = :id"), {"id": event_id}
        )
    assert found == 1


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE audit_events SET action = 'tampered' WHERE id = :id",
        "DELETE FROM audit_events WHERE id = :id",
    ],
)
def test_app_role_cannot_update_or_delete(app_engine: Engine, statement: str) -> None:
    event_id = _insert_event(app_engine)
    with app_engine.connect() as conn, pytest.raises(ProgrammingError, match="permission denied"):
        conn.execute(text(statement), {"id": event_id})


def test_even_owner_cannot_rewrite_history(app_engine: Engine, owner_engine: Engine) -> None:
    event_id = _insert_event(app_engine)
    with owner_engine.connect() as conn, pytest.raises(DBAPIError, match="append-only"):
        conn.execute(text("DELETE FROM audit_events WHERE id = :id"), {"id": event_id})
