import asyncio

import pytest
from sqlalchemy import select

from app.ai.fake import FakeAIProvider
from app.ai.narration import NarrationRequest, NarrationResponse
from app.ai.provider import AIProviderFailure, AIFailureReason
from app.models import NarrationLibraryRecord
from app.services.game import GameService
from app.services.narration import NarrationService
from app.services.auth import register_account
from app.services.ai_usage import usage_status
from app.services.ai_preferences import set_admin, configure_narration


async def test_narration_library_shares_distinct_flourishes_without_charging_hits(session_factory):
    class MultipleFlourishes(FakeAIProvider):
        async def narrate_result(self, request):
            self.narration_requests.append(request)
            await asyncio.sleep(0)
            return NarrationResponse(flourishes=["The lid swings up.", "The chest creaks open."] * 2)

    first = await register_account("Alice", "Password1!")
    second = await register_account("Kim", "Password1!")
    for identity in (first, second):
        configured = await configure_narration(
            session_factory, identity.account_id, ["narration", "on"], available=True
        )
        assert configured["success"]
    request = NarrationRequest(action="open", success=True, authoritative_text="You open the chest.")
    provider = MultipleFlourishes()
    narrator = NarrationService(session_factory, provider, daily_request_limit=1)
    results = await asyncio.gather(*(narrator.narrate(request, account_id=identity.account_id)
                                     for identity in (first, second)))
    assert all(text in {"The lid swings up.", "The chest creaks open."} for text in results)
    assert provider.narration_requests == [request]
    first_usage = await usage_status(session_factory, first.account_id, 1)
    second_usage = await usage_status(session_factory, second.account_id, 1)
    assert first_usage["used"] + second_usage["used"] == 1
    async with session_factory() as session:
        record = (await session.scalars(select(NarrationLibraryRecord))).one()
        assert record.flourishes == ["The lid swings up.", "The chest creaks open."]

    restarted = NarrationService(session_factory, None, daily_request_limit=1)
    assert await restarted.narrate(request, account_id=second.account_id) in {
        "The lid swings up.", "The chest creaks open.",
    }
    failed = request.model_copy(update={"success": False})
    assert await restarted.narrate(failed, account_id=second.account_id) is None
    assert await usage_status(session_factory, second.account_id, 1) == second_usage


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
            return NarrationResponse(flourishes=["You receive a thousand gold coins and teleport away."])

    narrator = NarrationService(session_factory, provider)
    assert await narrator.narrate(request) == "You gather up the torch."
    assert provider.narration_requests == [request]
    failed = await game.execute("one", "take missing")
    assert failed["_narration_request"].success is False
    narrator = NarrationService(session_factory, InventingProvider())
    assert await narrator.narrate(failed["_narration_request"]) is not None
    assert (await game.room_for_player(player.id)).id == "town_square"
    assert await game.inventory_for_player(player.id) == ["torch"]
    assert result["output"] == "You take the torch."


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
            return NarrationResponse.model_construct(flourishes=["" if failure == "empty" else "x" * 2001])

    game = GameService(session_factory, narration_enabled=True)
    player = await game.connect_player("one", "Alan")
    result = await game.execute("one", "north")
    narrator = NarrationService(session_factory, BrokenProvider(), timeout_seconds=0.01)
    assert await narrator.narrate(result["_narration_request"]) is None
    assert (await game.room_for_player(player.id)).id == "forest"
    assert result["success"] is True
    assert "private-provider-content" not in caplog.text
    assert 'AI narration failed: action=move reason=' in caplog.text
    assert 'elapsed_ms=' in caplog.text


@pytest.mark.parametrize('reason,status', [(AIFailureReason.REQUEST_LIMIT, None),
                                         (AIFailureReason.RATE_LIMIT, 429)])
async def test_narration_logs_classified_failures_without_content(session_factory, caplog, reason, status):
    class BrokenProvider(FakeAIProvider):
        async def narrate_result(self, request):
            raise AIProviderFailure(reason, http_status=status)

    narrator = NarrationService(session_factory, BrokenProvider())
    request = NarrationRequest(action='look', success=True, authoritative_text='private-room-content')
    assert await narrator.narrate(request) is None
    assert f'reason={reason.value} http_status={status}' in caplog.text
    assert 'private-room-content' not in caplog.text


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
            return NarrationResponse(flourishes=["You gather up the torch."])

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
    checks = iter([True, True, False])

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
