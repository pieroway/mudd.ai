import asyncio
from datetime import timedelta
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from app.ai.fake import FakeAIProvider
from app.models.ai_usage import AIUsageRecord
from app.services.ai_usage import reserve_attempt, usage_status, utc_day
from app.services.auth import register_account
from app.services.game import GameService


async def test_failed_reservation_never_calls_provider(session_factory, monkeypatch):
    from app.services import game

    provider = FakeAIProvider()
    service = GameService(session_factory, ai_provider=provider)
    await service.connect_player("one", "Alice")
    monkeypatch.setattr(
        game, "reserve_attempt", AsyncMock(side_effect=RuntimeError("database unavailable"))
    )
    with pytest.raises(RuntimeError):
        await service.execute("one", "walk toward the docks", account_id="account")
    assert provider.requests == []


async def test_disabled_ai_does_not_consume_budget(session_factory):
    identity = await register_account("Alice", "Password1!")
    service = GameService(session_factory)
    await service.connect_player("one", identity.username, player_id=identity.player_id)
    await service.execute("one", "walk toward the docks", account_id=identity.account_id)
    assert (await usage_status(session_factory, identity.account_id, 1))["used"] == 0


async def test_concurrent_reservations_never_exceed_limit(session_factory):
    identity = await register_account("Alice", "Password1!")
    results = await asyncio.gather(
        *[reserve_attempt(session_factory, identity.account_id, 3) for _ in range(12)]
    )
    assert sum(results) == 3
    status = await usage_status(session_factory, identity.account_id, 3)
    assert status["used"] == 3
    assert status["remaining"] == 0


async def test_old_day_and_other_account_do_not_consume_today(session_factory):
    alice = await register_account("Alice", "Password1!")
    bob = await register_account("Bob", "Password1!")
    async with session_factory() as session:
        async with session.begin():
            today = await session.scalar(select(utc_day()))
            session.add(
                AIUsageRecord(
                    account_id=alice.account_id, day=today - timedelta(days=1), attempts=20
                )
            )
    assert await reserve_attempt(session_factory, bob.account_id, 1)
    assert (await usage_status(session_factory, alice.account_id, 1))["used"] == 0
    assert await reserve_attempt(session_factory, alice.account_id, 1)


async def test_zero_and_lowered_limit_deny_further_reservations(session_factory):
    identity = await register_account("Alice", "Password1!")
    assert not await reserve_attempt(session_factory, identity.account_id, 0)
    assert await reserve_attempt(session_factory, identity.account_id, 2)
    assert not await reserve_attempt(session_factory, identity.account_id, 1)
    assert (await usage_status(session_factory, identity.account_id, 0))["remaining"] == 0


async def test_restart_preserves_budget_failures_count_and_classic_still_works(session_factory):
    identity = await register_account("Alice", "Password1!")
    provider = FakeAIProvider()
    service = GameService(session_factory, ai_provider=provider, ai_daily_request_limit=1)
    await service.connect_player("one", identity.username, player_id=identity.player_id)
    result = await service.execute(
        "one", "unsupported natural request", account_id=identity.account_id
    )
    assert not result["success"]
    assert len(provider.requests) == 1
    await service.disconnect_player("one")
    restarted = GameService(session_factory, ai_provider=provider, ai_daily_request_limit=1)
    await restarted.connect_player("two", identity.username, player_id=identity.player_id)
    denied = await restarted.execute("two", "walk toward the docks", account_id=identity.account_id)
    assert "allowance exhausted" in denied["output"]
    assert len(provider.requests) == 1
    assert (await restarted.execute("two", "north", account_id=identity.account_id))["success"]
    assert (await usage_status(session_factory, identity.account_id, 1))["used"] == 1


def test_websocket_reports_own_usage_and_enforces_allowance(test_client, monkeypatch):
    from app.api import websocket

    monkeypatch.setattr(
        websocket.game_service,
        "ai_provider",
        FakeAIProvider(
            {"please study the torch": {"command": {"action": "examine", "target": "torch"}}}
        ),
    )
    monkeypatch.setattr(websocket.game_service, "ai_daily_request_limit", 1)
    monkeypatch.setattr(websocket.settings, "ai_daily_request_limit", 1)
    origin = {"origin": "http://localhost:5173"}
    assert (
        test_client.post(
            "/auth/register",
            headers=origin,
            json={
                "username": "Alice",
                "password": "Password1!",
            },
        ).status_code
        == 201
    )
    with test_client.websocket_connect("/ws?account_id=other", headers=origin) as ws:
        assert ws.receive_json()["ai_usage"]["remaining"] == 1
        ws.send_text("please study the torch")
        assert ws.receive_json()["ai_usage"]["remaining"] == 0
        ws.send_text("please study the torch")
        assert "allowance exhausted" in ws.receive_json()["text"]
        ws.send_text("look")
        assert ws.receive_json()["success"]
    with test_client.websocket_connect("/ws", headers=origin) as ws:
        assert ws.receive_json()["ai_usage"]["remaining"] == 0
