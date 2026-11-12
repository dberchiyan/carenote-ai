"""Drop the never-visible `extracted` note status.

Extraction and review are one step: the draft is ready for the nurse the moment it exists.

Revision ID: 0003
Revises: 0002
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0003"
down_revision: str | Sequence[str] | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OLD = ("uploaded", "transcribed", "extracted", "in_review", "confirmed", "rejected")
NEW = ("uploaded", "transcribed", "in_review", "confirmed", "rejected")


def _swap_enum(values: tuple[str, ...], remap: dict[str, str]) -> None:
    """Postgres cannot remove an enum value: rebuild the type and recast the column."""
    quoted = ", ".join(f"'{v}'" for v in values)
    op.execute("ALTER TYPE note_status RENAME TO note_status_old")
    op.execute(f"CREATE TYPE note_status AS ENUM ({quoted})")
    for old, new in remap.items():
        # Values come from the tuples above, never from input.
        op.execute(f"UPDATE voice_notes SET status = '{new}' WHERE status = '{old}'")  # noqa: S608
    op.execute(
        "ALTER TABLE voice_notes ALTER COLUMN status TYPE note_status "
        "USING status::text::note_status"
    )
    op.execute("DROP TYPE note_status_old")


def upgrade() -> None:
    _swap_enum(NEW, {"extracted": "in_review"})


def downgrade() -> None:
    _swap_enum(OLD, {})
