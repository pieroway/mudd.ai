import pytest
from sqlalchemy import update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db import engine
from app.models import AccountRecord
from app.services.auth import register_account
from app.services.moderation import moderate
from app.services.roles import bootstrap_god, change_role


async def test_god_is_bound_to_alan_and_protected():
    alan = await register_account("Alan", "Testing-123!")
    admin = await register_account("OtherAdmin", "Testing-123!")
    async with engine.connect() as connection, connection.begin() as transaction:
        factory = async_sessionmaker(connection, expire_on_commit=False, join_transaction_mode="create_savepoint")
        await bootstrap_god(factory)
        await bootstrap_god(factory)
        await change_role(factory, alan.account_id, "OtherAdmin", "admin", True)
        assert await change_role(factory, admin.account_id, "Alan", None, False) == (
            "Assigned roles: god, admin, moderator, creator."
        )
        for actor_id in (admin.account_id, None):
            with pytest.raises(ValueError, match="protected"):
                await change_role(factory, actor_id, "Alan", "admin", False)
        assert not (await moderate(factory, admin.account_id, "admin", {
            "admin": admin.player_id, "alan": alan.player_id,
        }, ["boot", "Alan", "Test"]))["success"]
        with pytest.raises(DBAPIError, match="protected"):
            async with connection.begin_nested():
                await connection.execute(update(AccountRecord).where(
                    AccountRecord.id == alan.account_id).values(is_god=False))
        await transaction.rollback()
