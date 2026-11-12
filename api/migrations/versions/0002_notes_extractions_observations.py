"""voice notes, extraction drafts, confirmed observations

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from migrations.helpers import grant_read_write
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NOTE_STATUS = ("uploaded", "transcribed", "extracted", "in_review", "confirmed", "rejected")


def upgrade() -> None:
    op.create_table(
        "voice_notes",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("ward", sa.String(32), nullable=False),
        sa.Column("patient_id", sa.Uuid(), sa.ForeignKey("patients.id")),
        sa.Column("author_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("source", sa.String(16), nullable=False),
        sa.Column("audio_path", sa.String(512)),
        sa.Column("audio_mime", sa.String(64)),
        sa.Column("audio_duration_s", sa.Float()),
        sa.Column("status", sa.Enum(*NOTE_STATUS, name="note_status"), nullable=False),
        sa.Column("transcript", sa.Text()),
        sa.Column("redacted_transcript", sa.Text()),
        sa.Column("redaction_map", postgresql.JSONB()),
        sa.Column("patient_candidates", postgresql.JSONB()),
        sa.Column("match_status", sa.String(16)),
        sa.Column("timings_ms", postgresql.JSONB()),
        sa.Column("error_step", sa.String(16)),
        sa.Column("error_message", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True)),
        sa.Column("confirmed_by", sa.Uuid(), sa.ForeignKey("users.id")),
    )
    op.create_index("ix_voice_notes_ward", "voice_notes", ["ward"])
    op.create_index("ix_voice_notes_patient_id", "voice_notes", ["patient_id"])
    op.create_index("ix_voice_notes_status", "voice_notes", ["status"])
    op.create_index("ix_voice_notes_created_at", "voice_notes", ["created_at"])

    op.create_table(
        "extractions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("note_id", sa.Uuid(), sa.ForeignKey("voice_notes.id"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("source", sa.String(16), nullable=False),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("model", sa.String(64)),
        sa.Column("prompt_version", sa.String(32)),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("cost_usd", sa.Float(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("note_id", "version"),
    )
    op.create_index("ix_extractions_note_id", "extractions", ["note_id"])

    op.create_table(
        "confirmed_observations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("note_id", sa.Uuid(), sa.ForeignKey("voice_notes.id"), nullable=False),
        sa.Column("patient_id", sa.Uuid(), sa.ForeignKey("patients.id"), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("code", sa.String(16), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("unit", sa.String(16), nullable=False),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("flag", sa.String(16), nullable=False),
    )
    op.create_index("ix_confirmed_observations_note_id", "confirmed_observations", ["note_id"])
    op.create_index(
        "ix_confirmed_observations_patient_id", "confirmed_observations", ["patient_id"]
    )
    op.create_index(
        "ix_confirmed_observations_effective_at", "confirmed_observations", ["effective_at"]
    )

    grant_read_write("voice_notes", "extractions", "confirmed_observations")


def downgrade() -> None:
    op.drop_table("confirmed_observations")
    op.drop_table("extractions")
    op.drop_table("voice_notes")
    op.execute("DROP TYPE note_status")
