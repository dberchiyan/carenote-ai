"""users, patients, append-only audit_events

Revision ID: 0001
Revises:
Create Date: 2026-11-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from migrations.helpers import ensure_app_role, grant_append_only, grant_read_write
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    ensure_app_role()

    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("username", sa.String(64), nullable=False, unique=True),
        sa.Column("display_name", sa.String(128), nullable=False),
        sa.Column(
            "role",
            sa.Enum("nurse", "charge_nurse", "auditor", name="role"),
            nullable=False,
        ),
        sa.Column("ward", sa.String(32)),
    )
    op.create_table(
        "patients",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("mrn", sa.String(32), nullable=False, unique=True),
        sa.Column("given_name", sa.String(64), nullable=False),
        sa.Column("family_name", sa.String(64), nullable=False),
        sa.Column("birth_date", sa.Date(), nullable=False),
        sa.Column("sex", sa.String(16), nullable=False),
        sa.Column("ward", sa.String(32), nullable=False),
        sa.Column("room", sa.String(16), nullable=False),
    )
    op.create_index("ix_patients_ward", "patients", ["ward"])
    op.create_table(
        "audit_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("actor_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("entity", sa.String(64), nullable=False),
        sa.Column("entity_id", sa.String(64)),
        sa.Column("before", postgresql.JSONB()),
        sa.Column("after", postgresql.JSONB()),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_audit_events_actor_id", "audit_events", ["actor_id"])
    op.create_index("ix_audit_events_action", "audit_events", ["action"])
    op.create_index("ix_audit_events_at", "audit_events", ["at"])
    op.create_index("ix_audit_events_entity", "audit_events", ["entity", "entity_id"])

    grant_read_write("users", "patients")
    grant_append_only("audit_events")

    # Defence in depth: even the table owner cannot rewrite history.
    op.execute(
        """
        CREATE FUNCTION audit_events_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          RAISE EXCEPTION 'audit_events is append-only';
        END $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER audit_events_no_update_delete
        BEFORE UPDATE OR DELETE ON audit_events
        FOR EACH ROW EXECUTE FUNCTION audit_events_immutable();
        """
    )
    op.execute(
        """
        CREATE TRIGGER audit_events_no_truncate
        BEFORE TRUNCATE ON audit_events
        FOR EACH STATEMENT EXECUTE FUNCTION audit_events_immutable();
        """
    )


def downgrade() -> None:
    op.drop_table("audit_events")
    op.execute("DROP FUNCTION audit_events_immutable()")
    op.drop_table("patients")
    op.drop_table("users")
    op.execute("DROP TYPE role")
