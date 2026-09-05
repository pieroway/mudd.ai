import pytest
from sqlalchemy import text

from app.config import Settings
from app.db import create_database_engine


async def test_runtime_pool_reuses_a_connection_after_transaction_rollback():
    engine = create_database_engine(Settings(database_pool_enabled=True))
    try:
        with pytest.raises(RuntimeError, match="rollback"):
            async with engine.begin() as connection:
                first_pid = await connection.scalar(text("SELECT pg_backend_pid()"))
                await connection.execute(text("CREATE TEMPORARY TABLE rollback_probe (id integer)"))
                raise RuntimeError("rollback")
        async with engine.begin() as connection:
            assert await connection.scalar(text("SELECT pg_backend_pid()")) == first_pid
            assert (
                await connection.scalar(text("SELECT to_regclass('pg_temp.rollback_probe')"))
                is None
            )
            assert await connection.scalar(text("SELECT 1")) == 1
    finally:
        await engine.dispose()
