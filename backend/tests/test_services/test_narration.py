import asyncio

import pytest

from app.ai.fake import FakeAIProvider
from app.ai.narration import NarrationRequest, NarrationResponse
from app.services.game import GameService
from app.services.narration import NarrationService
from app.services.auth import register_account
from app.services.ai_usage import usage_status
from app.services.ai_preferences import set_admin, configure_narration


async def test_narration_shares_allowance_and_failure_does_not_refund(session_factory):
    class BrokenProvider(FakeAIProvider):
        async def narrate_result(self, request):
            self.narration_requests.append(request)
            raise RuntimeError("unavailable")

    identity = await register_account("Alice", "Password1!")
    await set_admin(session_factory, "Alice", True)
    await configure_narration(session_factory, identity.account_id, ["narration", "on"], available=True)
    provider = BrokenProvider()
    game = GameService(session_factory, ai_provider=provider, narration_enabled=True,
                       ai_daily_request_limit=2)
    await game.connect_player("one", identity.username, player_id=identity.player_id)
    result = await game.execute("one", "walk toward the docks", account_id=identity.account_id)
    narrator = NarrationService(session_factory, provider, daily_request_limit=2)
    assert await narrator.narrate(
        result["_narration_request"], account_id=identity.account_id
    ) is None
    assert (await usage_status(session_factory, identity.account_id, 2))["used"] == 2
    assert await narrator.narrate(
        result["_narration_request"], account_id=identity.account_id
    ) is None
    assert len(provider.narration_requests) == 1
    assert (await game.execute("one", "north"))["success"] is True


async def test_narration_receives_committed_outcome_without_mutating_world(session_factory):
    provider = FakeAIProvider()
    game = GameService(session_factory, narration_enabled=True)
    player = await game.connect_player("one", "Alan")
    result = await game.execute("one", "take torch")
    request = result.pop("_narration_request")
    assert request.model_dump() == {
        "action": "take", "success": True, "authoritative_text": "You take the torch."
    }
    assert await game.inventory_for_player(player.id) == ["torch"]

    class InventingProvider(FakeAIProvider):
        async def narrate_result(self, request):
            return NarrationResponse(text="You receive a thousand gold coins and teleport away.")

    narrator = NarrationService(session_factory, InventingProvider())
    assert await narrator.narrate(request) is not None
    assert (await game.room_for_player(player.id)).id == "town_square"
    assert await game.inventory_for_player(player.id) == ["torch"]
    assert result["output"] == "You take the torch."
    failed = await game.execute("one", "take missing")
    assert failed["_narration_request"].success is False
    narrator = NarrationService(session_factory, provider)
    assert await narrator.narrate(request) == "You gather up the torch."
    assert provider.narration_requests == [request]


@pytest.mark.parametrize("failure", ["timeout", "exception", "extra_fields", "empty", "oversized"])
async def test_narration_failures_preserve_completed_action(session_factory, failure, caplog):
    class BrokenProvider(FakeAIProvider):
        async def narrate_result(self, request):
            if failure == "timeout":
                await asyncio.sleep(1)
            if failure == "exception":
                raise RuntimeError("private-provider-content")
            if failure == "extra_fields":
                return {"text": "Done", "success": True, "inventory": ["gold"]}
            return NarrationResponse.model_construct(text="" if failure == "empty" else "x" * 2001)

    game = GameService(session_factory, narration_enabled=True)
    player = await game.connect_player("one", "Alan")
    result = await game.execute("one", "north")
    narrator = NarrationService(session_factory, BrokenProvider(), timeout_seconds=0.01)
    assert await narrator.narrate(result["_narration_request"]) is None
    assert (await game.room_for_player(player.id)).id == "forest"
    assert result["success"] is True
    assert "private-provider-content" not in caplog.text


async def test_disabled_narration_and_private_commands_have_no_context(session_factory):
    game = GameService(session_factory)
    await game.connect_player("one", "Alan")
    assert "_narration_request" not in await game.execute("one", "north")
    game.narration_enabled = True
    for command in ["say private-message", "tell Alan private-message", "who", "help", "inventory"]:
        assert "_narration_request" not in await game.execute("one", command)


async def test_narration_does_not_hold_game_lock(session_factory):
    started, release = asyncio.Event(), asyncio.Event()

    class SlowProvider(FakeAIProvider):
        async def narrate_result(self, request):
            started.set()
            await release.wait()
            return NarrationResponse(text="You gather up the torch.")

    game = GameService(session_factory, narration_enabled=True)
    await game.connect_player("one", "Alan")
    await game.connect_player("two", "Kim")
    result = await game.execute("one", "take torch")
    narrator = NarrationService(session_factory, SlowProvider())
    task = asyncio.create_task(narrator.narrate(result["_narration_request"]))
    try:
        await asyncio.wait_for(started.wait(), 1)
        second = await asyncio.wait_for(game.execute("two", "north"), 1)
        assert second["success"] is True
    finally:
        release.set()
        await task


async def test_narration_rechecks_authorization_after_provider(session_factory):
    checks = iter([True, False])

    async def authorized():
        return next(checks)

    provider = FakeAIProvider()
    narrator = NarrationService(session_factory, provider)
    request = NarrationRequest(action="take", success=True, authoritative_text="You take the torch.")
    assert await narrator.narrate(request, authorization_check=authorized) is None
    assert len(provider.narration_requests) == 1


async def test_narration_denied_authorization_never_calls_provider(session_factory):
    async def authorized():
        return False

    provider = FakeAIProvider()
    narrator = NarrationService(session_factory, provider)
    request = NarrationRequest(action="take", success=True, authoritative_text="You take the torch.")
    assert await narrator.narrate(request, authorization_check=authorized) is None
    assert not provider.narration_requests
