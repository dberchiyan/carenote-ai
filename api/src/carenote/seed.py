"""Seed demo users and synthetic patients. Idempotent. Usage: python -m carenote.seed

`--history` also replaces all notes with a week of synthetic ward history (see demo_history).
"""

import argparse

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from carenote.auth.models import Role, User
from carenote.db import get_sessionmaker
from carenote.demo_history import reset_notes, seed_history
from carenote.patients.models import Patient
from carenote.patients.synthetic import generate_patients

# username, display name, role, ward. The first three are offered on the login screen;
# "nurse_b" exists so ward isolation can be demonstrated and tested.
DEMO_USERS: tuple[tuple[str, str, Role, str | None], ...] = (
    ("nurse", "Nora Lindqvist", Role.NURSE, "3A"),
    ("charge", "Carlos Mendes", Role.CHARGE_NURSE, "3A"),
    ("auditor", "Aisha Rahman", Role.AUDITOR, None),
    ("nurse_b", "Ben Okafor", Role.NURSE, "3B"),
)


def seed(session: Session) -> None:
    for username, display_name, role, ward in DEMO_USERS:
        session.execute(
            insert(User)
            .values(username=username, display_name=display_name, role=role, ward=ward)
            .on_conflict_do_nothing(index_elements=[User.username])
        )
    for p in generate_patients():
        session.execute(
            insert(Patient)
            .values(
                id=p.id,
                mrn=p.mrn,
                given_name=p.given_name,
                family_name=p.family_name,
                birth_date=p.birth_date,
                sex=p.sex,
                ward=p.ward,
                room=p.room,
            )
            .on_conflict_do_nothing(index_elements=[Patient.mrn])
        )
    session.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--history",
        action="store_true",
        help="delete all notes and generate a week of synthetic history",
    )
    args = parser.parse_args()
    with get_sessionmaker()() as session:
        seed(session)
        print(f"Seeded {len(DEMO_USERS)} demo users and {len(generate_patients())} patients.")
        if args.history:
            reset_notes(session)
            notes = seed_history(session)
            session.commit()
            print(f"Replaced notes with {notes} synthetic notes over the past week.")


if __name__ == "__main__":
    main()
