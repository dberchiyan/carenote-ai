"""Shared migration helpers: privileges for the restricted runtime role."""

from alembic import op

APP_ROLE = "carenote_app"


def ensure_app_role() -> None:
    # Normally created with LOGIN + password by the db init script; NOLOGIN fallback keeps
    # migrations runnable on a bare server (e.g. CI), where the test fixture sets a password.
    op.execute(
        f"""
        DO $$ BEGIN
          IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '{APP_ROLE}') THEN
            CREATE ROLE {APP_ROLE} NOLOGIN;
          END IF;
        END $$;
        """
    )
    op.execute(f"GRANT USAGE ON SCHEMA public TO {APP_ROLE}")


def grant_read_write(*tables: str) -> None:
    for table in tables:
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO {APP_ROLE}")


def grant_append_only(*tables: str) -> None:
    for table in tables:
        op.execute(f"REVOKE ALL ON {table} FROM {APP_ROLE}")
        op.execute(f"GRANT SELECT, INSERT ON {table} TO {APP_ROLE}")
