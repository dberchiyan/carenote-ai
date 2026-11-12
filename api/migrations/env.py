"""Alembic environment. The database URL comes from application settings (env vars)."""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

import carenote.models  # noqa: F401 - registers all models on Base.metadata
from carenote.config import get_settings
from carenote.db import Base

config = context.config
if config.config_file_name is not None:
    # Keep the app's loggers alive: tests migrate in-process, and the default would silence them.
    fileConfig(config.config_file_name, disable_existing_loggers=False)

# Tests pass an explicit URL via config attributes; otherwise use the owner (migration) URL.
if not config.attributes.get("skip_url_from_settings"):
    settings = get_settings()
    config.set_main_option(
        "sqlalchemy.url", settings.migration_database_url or settings.database_url
    )
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
