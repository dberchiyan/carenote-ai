"""Rules version on observations, CHECK constraints, and the indexes the hot queries need.

Revision ID: 0005
Revises: 0004
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | Sequence[str] | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Frozen copies: a migration must not follow the code's enums as they evolve.
VITAL_KINDS = (
    "systolic_bp", "diastolic_bp", "heart_rate", "respiratory_rate", "temperature", "spo2",
    "weight", "blood_glucose",
)  # fmt: skip
FLAGS = ("normal", "warning", "critical")


def _in(column: str, values: Sequence[str]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


def upgrade() -> None:
    # Every stored observation so far was flagged with rules version 1.
    op.add_column(
        "confirmed_observations",
        sa.Column("rules_version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.create_check_constraint(
        "ck_voice_notes_source", "voice_notes", _in("source", ("audio", "text"))
    )
    op.create_check_constraint(
        "ck_extractions_source", "extractions", _in("source", ("ai", "nurse"))
    )
    op.create_check_constraint(
        "ck_confirmed_observations_flag", "confirmed_observations", _in("flag", FLAGS)
    )
    op.create_check_constraint(
        "ck_confirmed_observations_kind", "confirmed_observations", _in("kind", VITAL_KINDS)
    )
    # "My recent notes" and "latest value per vital for a ward": one index scan each.
    op.create_index("ix_voice_notes_author_created", "voice_notes", ["author_id", "created_at"])
    op.create_index(
        "ix_confirmed_observations_patient_kind_effective",
        "confirmed_observations",
        ["patient_id", "kind", "effective_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_confirmed_observations_patient_kind_effective", "confirmed_observations")
    op.drop_index("ix_voice_notes_author_created", "voice_notes")
    op.drop_constraint("ck_confirmed_observations_kind", "confirmed_observations", type_="check")
    op.drop_constraint("ck_confirmed_observations_flag", "confirmed_observations", type_="check")
    op.drop_constraint("ck_extractions_source", "extractions", type_="check")
    op.drop_constraint("ck_voice_notes_source", "voice_notes", type_="check")
    op.drop_column("confirmed_observations", "rules_version")
