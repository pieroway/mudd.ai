import asyncio

import pytest

from app.ai.fake import FakeAIProvider
from app.ai.models import InterpretCommandRequest, InterpretCommandResponse
from app.ai.provider import AIProvider
from app.services.game import GameService, UsernameInUseError


@pytest.mark.asyncio
async def test_reconnect_restores_player_location_and_inventory(session_factory):
    service = GameService(session_factory)
    first_connection = await service.connect_player("connection-1", "Alan")
    await service.execute("connection-1", "take torch")
    await service.execute("connection-1", "north")
    await service.disconnect_player("connection-1")

    restarted_service = GameService(session_factory)
    second_connection = await restarted_service.connect_player("connection-2", "alan")

    assert second_connection.id == first_connection.id
    assert second_connection.current_room_id == "forest"
    assert second_connection.inventory == ["torch"]


@pytest.mark.asyncio
async def test_normalized_username_must_be_unique_while_connected(session_factory):
    service = GameService(session_factory)
    await service.connect_player("connection-1", "Alan")

    with pytest.raises(UsernameInUseError):
        await service.connect_player("connection-2", "  ALAN  ")


@pytest.mark.asyncio
async def test_only_one_player_can_take_a_shared_item_concurrently(session_factory):
    service = GameService(session_factory)
    first_player = await service.connect_player("connection-1", "Alan")
    second_player = await service.connect_player("connection-2", "Robin")

    first_result, second_result = await asyncio.gather(
        service.execute("connection-1", "take torch"),
        service.execute("connection-2", "take torch"),
    )

    successes = [result for result in (first_result, second_result) if result["success"]]
    failures = [result for result in (first_result, second_result) if not result["success"]]
    assert len(successes) == 1
    assert failures == [
        {
            "success": False,
            "output": "You do not see a torch here.",
            "metadata": {"command_source": "classic"},
        }
    ]

    first_inventory = await service.inventory_for_player(first_player.id)
    second_inventory = await service.inventory_for_player(second_player.id)
    assert sorted(first_inventory + second_inventory) == ["torch"]


@pytest.mark.asyncio
async def test_open_item_state_survives_service_restart(session_factory):
    service = GameService(session_factory)
    await service.connect_player("connection-1", "Alan")

    result = await service.execute("connection-1", "open chest")
    await service.disconnect_player("connection-1")

    restarted_service = GameService(session_factory)
    await restarted_service.connect_player("connection-2", "Alan")
    repeated_result = await restarted_service.execute("connection-2", "open chest")

    assert result == {
        "success": True,
        "output": "You open the chest.",
        "metadata": {"command_source": "classic"},
    }
    assert repeated_result == {
        "success": False,
        "output": "The chest is already open.",
        "metadata": {"command_source": "classic"},
    }


@pytest.mark.asyncio
async def test_container_contents_survive_service_restart(session_factory):
    service = GameService(session_factory)
    await service.connect_player("connection-1", "Alan")
    await service.execute("connection-1", "take torch")
    await service.execute("connection-1", "open chest")
    put_result = await service.execute("connection-1", "put torch in chest")
    await service.disconnect_player("connection-1")

    restarted_service = GameService(session_factory)
    await restarted_service.connect_player("connection-2", "Alan")
    take_result = await restarted_service.execute(
        "connection-2", "take torch from chest"
    )

    assert put_result == {
        "success": True,
        "output": "You put the torch in the chest.",
        "metadata": {"command_source": "classic"},
    }
    assert take_result == {
        "success": True,
        "output": "You take the torch from the chest.",
        "metadata": {"command_source": "classic"},
    }


@pytest.mark.asyncio
async def test_lit_torch_state_survives_service_restart(session_factory):
    service = GameService(session_factory)
    await service.connect_player("connection-1", "Alan")
    await service.execute("connection-1", "take torch")
    await service.execute("connection-1", "use torch")
    await service.disconnect_player("connection-1")

    restarted_service = GameService(session_factory)
    await restarted_service.connect_player("connection-2", "Alan")
    result = await restarted_service.execute("connection-2", "look")

    assert "Torchlight reaches farther" in result["output"]


@pytest.mark.asyncio
async def test_torch_fuel_survives_service_restart(session_factory):
    service = GameService(session_factory)
    await service.connect_player("connection-1", "Alan")
    await service.execute("connection-1", "take torch")
    await service.execute("connection-1", "use torch")
    for _ in range(5):
        await service.execute("connection-1", "north")
        await service.execute("connection-1", "south")
    await service.disconnect_player("connection-1")

    restarted_service = GameService(session_factory)
    await restarted_service.connect_player("connection-2", "Alan")
    result = await restarted_service.execute("connection-2", "examine torch")

    assert "has some fuel remaining" in result["output"]


@pytest.mark.asyncio
async def test_classic_commands_do_not_call_ai_provider(session_factory):
    provider = FakeAIProvider()
    service = GameService(session_factory, ai_provider=provider)
    await service.connect_player("connection-1", "Alan")

    result = await service.execute("connection-1", "look")

    assert result["success"] is True
    assert result["metadata"] == {"command_source": "classic"}
    assert provider.requests == []


@pytest.mark.asyncio
async def test_unknown_commands_use_ai_proposal_then_authoritative_engine(session_factory):
    provider = FakeAIProvider()
    service = GameService(session_factory, ai_provider=provider)
    player = await service.connect_player("connection-1", "Alan")

    result = await service.execute("connection-1", "walk toward the docks")

    assert result["success"] is True
    assert result["metadata"] == {"command_source": "ai"}
    assert (await service.room_for_player(player.id)).id == "docks"
    assert provider.requests == [
        InterpretCommandRequest(raw_input="walk toward the docks")
    ]


@pytest.mark.asyncio
async def test_unavailable_interpretation_returns_safe_error_without_mutation(session_factory):
    provider = FakeAIProvider()
    service = GameService(session_factory, ai_provider=provider)
    player = await service.connect_player("connection-1", "Alan")

    result = await service.execute("connection-1", "perform an undocumented action")

    assert result == {
        "success": False,
        "output": "I couldn't interpret that command. Try 'help' for available commands.",
        "metadata": {"command_source": "ai"},
    }
    assert (await service.room_for_player(player.id)).id == "town_square"


class InvalidResponseProvider(AIProvider):
    async def interpret_command(
        self, request: InterpretCommandRequest
    ) -> InterpretCommandResponse:
        return {  # type: ignore[return-value]
            "command": {"action": "teleport", "direction": "north"}
        }


@pytest.mark.asyncio
async def test_provider_response_is_revalidated_before_engine_execution(session_factory):
    service = GameService(session_factory, ai_provider=InvalidResponseProvider())
    player = await service.connect_player("connection-1", "Alan")

    result = await service.execute("connection-1", "teleport north")

    assert result["success"] is False
    assert (await service.room_for_player(player.id)).id == "town_square"


class NeverRespondingProvider(AIProvider):
    async def interpret_command(
        self, request: InterpretCommandRequest
    ) -> InterpretCommandResponse:
        await asyncio.Event().wait()
        raise AssertionError("unreachable")


@pytest.mark.asyncio
async def test_provider_timeout_returns_safe_error_without_mutation(session_factory):
    service = GameService(
        session_factory,
        ai_provider=NeverRespondingProvider(),
        ai_command_timeout_seconds=0.001,
    )
    player = await service.connect_player("connection-1", "Alan")

    result = await service.execute("connection-1", "venture somewhere mysterious")

    assert result == {
        "success": False,
        "output": "I couldn't interpret that command. Try 'help' for available commands.",
        "metadata": {"command_source": "ai"},
    }
    assert (await service.room_for_player(player.id)).id == "town_square"
