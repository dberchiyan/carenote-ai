"""Test fixtures. Tests run against a real PostgreSQL (`docker compose up -d db`).

A fresh `carenote_test` database is migrated once per session; every test runs inside a
transaction that is rolled back, so route-level commits never leak between tests.
"""

import os

os.environ.setdefault("CARENOTE_ENV", "test")
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from dotenv import load_dotenv
from fastapi.testclient import TestClient
from sqlalchemy import Connection, Engine, create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from carenote.db import get_session, get_session_factory
from carenote.main import create_app
from carenote.providers.factory import get_llm, get_transcription
from carenote.providers.fake import FakeTranscription, RuleBasedLLM
from carenote.seed import seed

API_DIR = Path(__file__).resolve().parents[1]

# Where to create the throwaway test database. Local developers set CARENOTE_TEST_ADMIN_URL in
# .env (the external database, over the SSH tunnel); CI's Postgres service matches the default.
load_dotenv(API_DIR.parent / ".env")
ADMIN_URL = os.environ.get(
    "CARENOTE_TEST_ADMIN_URL", "postgresql+psycopg://carenote:carenote@localhost:5432/postgres"
)
# One throwaway database per xdist worker (gw0, gw1, ...) so `pytest -n auto` runs in parallel.
TEST_DB = "carenote_test_" + os.environ.get("PYTEST_XDIST_WORKER", "main")
# The runtime role the API uses. The migrations grant to it by name, so tests must use the same
# role; its password comes from the environment (.env locally, the CI default otherwise). Tests
# only ever CREATE it when missing: they never change a role the running app depends on.
APP_ROLE = "carenote_app"
APP_PASSWORD = os.environ.get("APP_DB_PASSWORD", "carenote_app")


def _url(user: str, password: str) -> str:
    return (
        make_url(ADMIN_URL)
        .set(username=user, password=password, database=TEST_DB)
        .render_as_string(hide_password=False)
    )


OWNER_URL = _url(make_url(ADMIN_URL).username or "carenote", make_url(ADMIN_URL).password or "")
APP_URL = _url(APP_ROLE, APP_PASSWORD)


@pytest.fixture(scope="session")
def _database() -> None:
    admin = create_engine(ADMIN_URL, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS {TEST_DB} WITH (FORCE)"))
        conn.execute(text(f"CREATE DATABASE {TEST_DB}"))
        # Workers share the role: serialise its setup, or Postgres reports a concurrent update.
        conn.execute(text("SELECT pg_advisory_lock(424242)"))
        try:
            exists = conn.scalar(text("SELECT 1 FROM pg_roles WHERE rolname = :r"), {"r": APP_ROLE})
            if not exists:
                conn.execute(text(f"CREATE ROLE {APP_ROLE} LOGIN PASSWORD '{APP_PASSWORD}'"))
        finally:
            conn.execute(text("SELECT pg_advisory_unlock(424242)"))
    admin.dispose()

    cfg = Config(str(API_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(API_DIR / "migrations"))
    cfg.set_main_option("sqlalchemy.url", OWNER_URL)
    cfg.attributes["skip_url_from_settings"] = True
    command.upgrade(cfg, "head")


@pytest.fixture(scope="session")
def app_engine(_database: None) -> Iterator[Engine]:
    """Engine connecting as the restricted runtime role, like the real API."""
    engine = create_engine(APP_URL)
    with Session(engine) as session:
        seed(session)
    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def owner_engine(_database: None) -> Iterator[Engine]:
    engine = create_engine(OWNER_URL)
    yield engine
    engine.dispose()


@pytest.fixture
def connection(app_engine: Engine) -> Iterator[Connection]:
    with app_engine.connect() as conn:
        transaction = conn.begin()
        yield conn
        transaction.rollback()


@pytest.fixture
def db(connection: Connection) -> Iterator[Session]:
    with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
        yield session


@pytest.fixture
def llm() -> RuleBasedLLM:
    """The LLM used by the API under test. Records every request it receives."""
    return RuleBasedLLM(record=True)


@pytest.fixture
def transcriber() -> FakeTranscription:
    return FakeTranscription()


@pytest.fixture
def client(
    connection: Connection, llm: RuleBasedLLM, transcriber: FakeTranscription
) -> Iterator[TestClient]:
    def make_session() -> Session:
        return Session(
            bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False
        )

    def session_override() -> Iterator[Session]:
        # Every test session shares one connection. Closing a session rolls back its open
        # savepoint, and FastAPI tears the request session down *after* background tasks ran,
        # which would discard their work. Release the savepoint first. (Production sessions use
        # separate connections, so this only applies to tests.)
        with make_session() as session:
            yield session
            if session.in_transaction():
                session.commit()

    app = create_app()
    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[get_session_factory] = lambda: make_session
    app.dependency_overrides[get_llm] = lambda: llm
    app.dependency_overrides[get_transcription] = lambda: transcriber
    with TestClient(app) as c:
        yield c


def login(client: TestClient, username: str) -> TestClient:
    response = client.post("/auth/demo-login", json={"username": username})
    assert response.status_code == 200, response.text
    return client
