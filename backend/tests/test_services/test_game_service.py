import asyncio

import pytest

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
    assert failures == [{"success": False, "output": "You do not see a torch here."}]

    first_inventory = await service.inventory_for_player(first_player.id)
    second_inventory = await service.inventory_for_player(second_player.id)
    assert sorted(first_inventory + second_inventory) == ["torch"]
