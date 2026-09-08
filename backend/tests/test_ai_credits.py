import asyncio
from datetime import timedelta

import pytest
from sqlalchemy import select

from app.ai.fake import FakeAIProvider
from app.config import Settings
from app.models import AccountRecord, AIUsageRecord
from app.models.ai_usage import AICreditGrantRecord
from app.services.ai_preferences import set_admin
from app.services.ai_usage import reserve_attempt, usage_status, utc_day
from app.services.auth import register_account
from app.services.game import GameService


async def setup_admin(session_factory):
    admin = await register_account("Admin", "Password1!")
    user = await register_account("Mary Jane", "Password1!")
    await set_admin(session_factory, "Admin", True)
    provider = FakeAIProvider()
    game = GameService(session_factory, ai_provider=provider)
    await game.connect_player("admin", admin.username, player_id=admin.player_id)
    return game, provider, admin, user


async def test_default_is_fifty_and_admin_can_grant_to_self_and_offline_user(session_factory):
    game, provider, admin, user = await setup_admin(session_factory)
    assert Settings(_env_file=None).ai_daily_request_limit == 50
    assert game.ai_daily_request_limit == 50
    result = await game.execute("admin", '/ai credits add "Mary Jane"', account_id=admin.account_id)
    assert result["success"] and "50" in result["output"]
    assert (await usage_status(session_factory, user.account_id, 50))["bonus_credits"] == 50
    result = await game.execute("admin", "/ai credits add Admin 75", account_id=admin.account_id)
    assert result["success"]
    status = await usage_status(session_factory, admin.account_id, 50)
    assert status["remaining"] == 125 and status["used"] == 0
    assert not provider.requests
    async with session_factory() as session:
        grants = (await session.scalars(select(AICreditGrantRecord))).all()
        assert sorted(grant.units for grant in grants) == [50, 75]
        assert all(grant.admin_account_id == admin.account_id for grant in grants)


@pytest.mark.parametrize("suffix", [
    "", "add", "add Nobody 50", 'add "Mary Jane" 0', 'add "Mary Jane" -1',
    'add "Mary Jane" 1.5', 'add "Mary Jane" 10001', 'add "Mary Jane" nope',
    'add "Mary Jane" 50 extra', 'add "Mary Jane',
])
async def test_invalid_grants_do_not_change_balances(session_factory, suffix):
    game, _, admin, user = await setup_admin(session_factory)
    assert not (await game.execute("admin", "/ai credits " + suffix, account_id=admin.account_id))["success"]
    assert (await usage_status(session_factory, user.account_id, 50))["bonus_credits"] == 0
    async with session_factory() as session:
        assert not (await session.scalars(select(AICreditGrantRecord))).all()


async def test_regular_revoked_and_expired_admin_cannot_grant(session_factory):
    game, provider, admin, user = await setup_admin(session_factory)
    await game.connect_player("user", user.username, player_id=user.player_id)
    assert not (await game.execute("user", "/ai credits add Admin", account_id=user.account_id))["success"]

    async def expired():
        return False

    assert not (await game.execute("admin", "/ai credits add Admin", account_id=admin.account_id,
                                   authorization_check=expired))["success"]
    await set_admin(session_factory, "Admin", False)
    assert not (await game.execute("admin", "/ai credits add Admin", account_id=admin.account_id))["success"]
    assert (await usage_status(session_factory, admin.account_id, 50))["bonus_credits"] == 0
    assert not provider.requests


async def test_daily_units_spent_first_and_bonus_survives_day_change(session_factory):
    game, _, admin, user = await setup_admin(session_factory)
    await game.execute("admin", '/ai credits add "Mary Jane" 3', account_id=admin.account_id)
    assert await reserve_attempt(session_factory, user.account_id, 1)
    assert (await usage_status(session_factory, user.account_id, 1))["bonus_credits"] == 3
    assert await reserve_attempt(session_factory, user.account_id, 1)
    status = await usage_status(session_factory, user.account_id, 1)
    assert status["daily_remaining"] == 0 and status["bonus_credits"] == 2
    async with session_factory() as session, session.begin():
        today = await session.scalar(select(utc_day()))
        record = await session.get(AIUsageRecord, (user.account_id, today))
        record.day = today - timedelta(days=1)
    status = await usage_status(session_factory, user.account_id, 1)
    assert status["daily_remaining"] == 1 and status["bonus_credits"] == 2
    assert status["remaining"] == 3


async def test_concurrent_reservations_cannot_double_spend_bonus(session_factory):
    game, _, admin, user = await setup_admin(session_factory)
    await game.execute("admin", '/ai credits add "Mary Jane" 3', account_id=admin.account_id)
    results = await asyncio.gather(*[
        reserve_attempt(session_factory, user.account_id, 2) for _ in range(12)
    ])
    assert sum(results) == 5
    status = await usage_status(session_factory, user.account_id, 2)
    assert status["remaining"] == 0 and status["used"] == 5
    assert status["bonus_credits"] == 0


async def test_concurrent_grants_are_additive_and_balance_is_capped(session_factory):
    game, _, admin, user = await setup_admin(session_factory)
    results = await asyncio.gather(*[
        game.execute("admin", '/ai credits add "Mary Jane" 10', account_id=admin.account_id)
        for _ in range(5)
    ])
    assert all(result["success"] for result in results)
    assert (await usage_status(session_factory, user.account_id, 50))["bonus_credits"] == 50
    async with session_factory() as session, session.begin():
        account = await session.get(AccountRecord, user.account_id)
        account.ai_bonus_credits = 1_000_000
    assert not (await game.execute("admin", '/ai credits add "Mary Jane"', account_id=admin.account_id))["success"]
    assert (await usage_status(session_factory, user.account_id, 50))["bonus_credits"] == 1_000_000


async def test_zero_limit_disables_spending_even_with_bonus(session_factory):
    game, _, admin, _ = await setup_admin(session_factory)
    await game.execute("admin", "/ai credits add Admin", account_id=admin.account_id)
    assert not await reserve_attempt(session_factory, admin.account_id, 0)
    status = await usage_status(session_factory, admin.account_id, 0)
    assert status["bonus_credits"] == 50 and status["remaining"] == 0
