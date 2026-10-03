"""Shared fixtures for the test suite.

The tests run against a real PostgreSQL database named in DATABASE_URL, which
must end in ``_test``. Once per run it is dropped, recreated and migrated with
Alembic, and the seed users are added. Before every test the request, history,
assignment and episode tables are truncated, so each test starts from the seed
users only. Users are kept between tests; a test that needs its own user
creates one with a unique email.
"""

import itertools
import os
from collections.abc import Callable, Iterator

import psycopg
import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import insert, select, text, update
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.db import SessionLocal, engine
from app.main import app
from app.models import Assignment, DatasetRequest, Episode, ExportJob, User
from app.seed import seed

TEST_URL = make_url(os.environ["DATABASE_URL"])
PASSWORDS = {
    "admin@example.com": "admin123",
    "ops1@example.com": "ops123",
    "ops2@example.com": "ops123",
    "client-a@example.com": "client123",
    "client-b@example.com": "client123",
}
_episode_numbers = itertools.count(1)


@pytest.fixture(scope="session", autouse=True)
def database() -> None:
    """Recreate the test database, run every migration and add the seed users."""
    if not TEST_URL.database.endswith("_test"):
        raise RuntimeError(f"Refusing to run tests against {TEST_URL.database!r}")
    server = TEST_URL.set(drivername="postgresql", database="postgres")
    with psycopg.connect(server.render_as_string(hide_password=False), autocommit=True) as conn:
        conn.execute(f'DROP DATABASE IF EXISTS "{TEST_URL.database}" WITH (FORCE)')
        conn.execute(f'CREATE DATABASE "{TEST_URL.database}"')
    command.upgrade(Config("alembic.ini"), "head")
    with SessionLocal() as session:
        seed(session)


@pytest.fixture(autouse=True)
def clean_tables() -> None:
    """Empty every table except users and organisations before each test."""
    with engine.begin() as connection:
        connection.execute(
            text(
                "TRUNCATE assignments, status_history, requests, episodes RESTART IDENTITY CASCADE"
            )
        )


@pytest.fixture
def db() -> Iterator[Session]:
    """Database session for setting up and inspecting data directly."""
    with SessionLocal() as session:
        yield session


def login(email: str, password: str | None = None) -> TestClient:
    """Return a test client holding a session cookie for this user."""
    client = TestClient(app)
    response = client.post(
        "/auth/login", json={"email": email, "password": password or PASSWORDS[email]}
    )
    assert response.status_code == 200, response.text
    return client


@pytest.fixture
def anon() -> TestClient:
    """Test client with no session."""
    return TestClient(app)


@pytest.fixture
def client_a() -> TestClient:
    """Client user of Acme Robotics."""
    return login("client-a@example.com")


@pytest.fixture
def client_b() -> TestClient:
    """Client user of Beta Labs."""
    return login("client-b@example.com")


@pytest.fixture
def operator() -> TestClient:
    """Operator user."""
    return login("ops1@example.com")


@pytest.fixture
def admin() -> TestClient:
    """Admin user."""
    return login("admin@example.com")


@pytest.fixture
def make_request(client_a: TestClient) -> Callable[..., int]:
    """Create a request through the API and return its id. Owned by client A by default."""

    def create(owner: TestClient | None = None, episodes_requested: int = 1) -> int:
        response = (owner or client_a).post(
            "/requests",
            json={
                "task_name": "pick cup",
                "episodes_requested": episodes_requested,
                "deadline": "2099-12-31",
            },
        )
        assert response.status_code == 201, response.text
        return response.json()["id"]

    return create


@pytest.fixture
def make_episodes(db: Session) -> Callable[..., list[str]]:
    """Insert episodes directly and return their episode_ids."""

    def create(count: int = 1, quality: str = "good") -> list[str]:
        ids = [f"EP-T{next(_episode_numbers):05d}" for _ in range(count)]
        db.execute(
            insert(Episode),
            [
                {
                    "episode_id": episode_id,
                    "robot_id": "arm-01",
                    "task_name": "pick cup",
                    "recorded_at": "2026-08-01T10:00:00+00:00",
                    "duration_seconds": 30,
                    "operator_name": "Tester",
                    "quality": quality,
                }
                for episode_id in ids
            ],
        )
        db.commit()
        return ids

    return create


def set_status(db: Session, request_id: int, status: str) -> None:
    """Put a request straight into a status, bypassing the workflow, to set up a test."""
    db.execute(update(DatasetRequest).where(DatasetRequest.id == request_id).values(status=status))
    db.commit()


def assign_directly(db: Session, request_id: int, episode_ids: list[str]) -> None:
    """Assign episodes by inserting rows directly, each with an already exported job."""
    operator_id = user_id(db, "ops1@example.com")
    for episode_id in episode_ids:
        episode = db.scalar(select(Episode).where(Episode.episode_id == episode_id))
        assignment = Assignment(
            episode_id=episode.id, request_id=request_id, assigned_by_id=operator_id
        )
        db.add(assignment)
        db.flush()
        db.add(ExportJob(assignment_id=assignment.id, max_attempts=5, status="succeeded"))
    db.commit()


def user_id(db: Session, email: str) -> int:
    """Return the id of the user with this email."""
    return db.scalar(select(User.id).where(User.email == email))


def status_of(db: Session, request_id: int) -> str:
    """Return the current status of a request, read from the database."""
    db.expire_all()
    return db.scalar(select(DatasetRequest.status).where(DatasetRequest.id == request_id))
