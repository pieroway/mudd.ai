from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import Settings

settings = Settings()


def create_database_engine(database_settings: Settings):
    if not database_settings.database_pool_enabled:
        # Pytest shares the engine across fixture and TestClient event loops.
        return create_async_engine(database_settings.database_url, poolclass=NullPool)
    return create_async_engine(
        database_settings.database_url,
        pool_size=5,
        max_overflow=5,
        pool_timeout=10,
        pool_pre_ping=True,
    )


engine = create_database_engine(settings)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    return async_session_factory
