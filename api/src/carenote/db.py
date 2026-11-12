"""Database engine, session factory and declarative base."""

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime
from functools import lru_cache
from typing import Any

from sqlalchemy import JSON, DateTime, Engine, Uuid, create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from carenote.config import get_settings

# JSONB on PostgreSQL, plain JSON elsewhere.
JsonType = JSON().with_variant(JSONB(), "postgresql")


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    type_annotation_map = {  # noqa: RUF012 - SQLAlchemy configuration attribute
        dict[str, Any]: JsonType,
        list[Any]: JsonType,
        datetime: DateTime(timezone=True),
        uuid.UUID: Uuid(),
    }


class UuidPk:
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)


@lru_cache
def get_engine() -> Engine:
    return create_engine(get_settings().database_url, pool_pre_ping=True)


@lru_cache
def get_sessionmaker() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), expire_on_commit=False)


def get_session() -> Iterator[Session]:
    """FastAPI dependency: one session per request."""
    with get_sessionmaker()() as session:
        yield session


def get_session_factory() -> sessionmaker[Session]:
    """FastAPI dependency for background work that outlives the request session."""
    return get_sessionmaker()
