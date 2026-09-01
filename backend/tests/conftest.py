"""Pytest configuration and fixtures."""

import pytest
import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Load test environment
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")


@pytest.fixture
async def db_session():
    """Create a test database session."""
    # For now, use in-memory SQLite
    # Later: use PostgreSQL test container
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with engine.begin() as conn:
        # Create tables (will add Base.metadata.create_all later)
        pass
    
    async with async_session() as session:
        yield session
    
    await engine.dispose()


@pytest.fixture
def test_client():
    """Create a FastAPI test client."""
    from fastapi.testclient import TestClient
    from app.main import app
    
    return TestClient(app)


@pytest.fixture
async def websocket_client():
    """Create a WebSocket test client."""
    # To be implemented with WebSocket testing utils
    pass
