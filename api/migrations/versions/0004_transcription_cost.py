"""Keep the transcription model and cost on the note, so metrics cover the whole pipeline.

Revision ID: 0004
Revises: 0003
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | Sequence[str] | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("voice_notes", sa.Column("transcription_model", sa.String(64), nullable=True))
    op.add_column(
        "voice_notes",
        sa.Column("transcription_cost_usd", sa.Float(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("voice_notes", "transcription_cost_usd")
    op.drop_column("voice_notes", "transcription_model")
