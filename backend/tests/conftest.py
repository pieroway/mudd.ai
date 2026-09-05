"""Pytest configuration and PostgreSQL fixtures."""

import os

import pytest
from sqlalchemy import delete

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("DATABASE_POOL_ENABLED", "false")

from app.db import get_session_factory  # noqa: E402
from app.db.seed import seed_world  # noqa: E402
from app.models import (  # noqa: E402
    AccountRecord,
    AuthSessionRecord,
    ExitRecord,
    ItemRecord,
    PlayerRecord,
    RoomRecord,
)  # noqa: E402


@pytest.fixture(autouse=True)
async def reset_persistent_database():
    """Give every test a deterministic PostgreSQL world."""
    factory = get_session_factory()
    from app.api.auth import attempts

    attempts.clear()
    async with factory() as session:
        async with session.begin():
            await session.execute(delete(AuthSessionRecord))
            await session.execute(delete(AccountRecord))
            await session.execute(delete(ItemRecord))
            await session.execute(delete(PlayerRecord))
            await session.execute(delete(ExitRecord))
            await session.execute(delete(RoomRecord))
            await seed_world(session)
    yield


@pytest.fixture
def session_factory():
    return get_session_factory()


@pytest.fixture
def test_client():
    """Create a client that runs the FastAPI lifespan hooks."""
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as client:
        yield client


@pytest.fixture
def seeded_world():
    """Create a deterministic in-memory world for pure engine tests."""
    from app.world import create_world

    return create_world()
