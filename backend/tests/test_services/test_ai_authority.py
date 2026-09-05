import asyncio

import pytest

from app.ai.fake import FakeAIProvider
from app.models import ItemRecord
from app.services.game import GameService


def provider_for(phrase: str, command: dict[str, object]) -> FakeAIProvider:
    return FakeAIProvider(fixtures={phrase: {"command": command}})


@pytest.mark.asyncio
async def test_ai_take_proposal_cannot_reach_item_in_another_room(session_factory):
    phrase = "pick the mushroom from here"
    service = GameService(
        session_factory,
        ai_provider=provider_for(phrase, {"action": "take", "target": "mushroom"}),
    )
    player = await service.connect_player("connection-1", "Alan")

    result = await service.execute("connection-1", phrase)

    assert result == {
        "success": False,
        "output": "You do not see a mushroom here.",
        "metadata": {"command_source": "ai"},
    }
    assert await service.inventory_for_player(player.id) == []


@pytest.mark.asyncio
async def test_ai_drop_proposal_cannot_move_another_players_item(session_factory):
    phrase = "discard the other player's torch"
    service = GameService(
        session_factory,
        ai_provider=provider_for(phrase, {"action": "drop", "target": "torch"}),
    )
    owner = await service.connect_player("connection-1", "Alan")
    other = await service.connect_player("connection-2", "Robin")
    await service.execute("connection-1", "take torch")

    result = await service.execute("connection-2", phrase)

    assert result["success"] is False
    assert result["metadata"] == {"command_source": "ai"}
    assert await service.inventory_for_player(owner.id) == ["torch"]
    assert await service.inventory_for_player(other.id) == []


@pytest.mark.asyncio
async def test_ai_take_from_proposal_cannot_bypass_closed_container(session_factory):
    phrase = "retrieve the torch from the closed chest"
    service = GameService(
        session_factory,
        ai_provider=provider_for(
            phrase,
            {"action": "take_from", "target": "torch", "container": "chest"},
        ),
    )
    player = await service.connect_player("connection-1", "Alan")
    await service.execute("connection-1", "take torch")
    await service.execute("connection-1", "open chest")
    await service.execute("connection-1", "put torch in chest")
    await service.execute("connection-1", "close chest")

    result = await service.execute("connection-1", phrase)

    assert result == {
        "success": False,
        "output": "The chest is closed.",
        "metadata": {"command_source": "ai"},
    }
    assert await service.inventory_for_player(player.id) == []


@pytest.mark.asyncio
async def test_ai_use_proposal_cannot_light_an_empty_torch(session_factory):
    phrase = "rekindle the exhausted torch"
    service = GameService(
        session_factory,
        ai_provider=provider_for(phrase, {"action": "use", "target": "torch"}),
    )
    player = await service.connect_player("connection-1", "Alan")
    await service.execute("connection-1", "take torch")
    async with session_factory() as session:
        async with session.begin():
            torch = await session.get(ItemRecord, "torch", with_for_update=True)
            assert torch is not None
            torch.fuel_remaining = 0
            torch.is_lit = False

    result = await service.execute("connection-1", phrase)

    assert result == {
        "success": False,
        "output": "The torch is out of fuel.",
        "metadata": {"command_source": "ai"},
    }
    assert await service.inventory_for_player(player.id) == ["torch"]


@pytest.mark.asyncio
async def test_concurrent_ai_take_proposals_cannot_duplicate_ownership(session_factory):
    phrase = "claim the nearby torch"
    service = GameService(
        session_factory,
        ai_provider=provider_for(phrase, {"action": "take", "target": "torch"}),
    )
    first = await service.connect_player("connection-1", "Alan")
    second = await service.connect_player("connection-2", "Robin")

    results = await asyncio.gather(
        service.execute("connection-1", phrase),
        service.execute("connection-2", phrase),
    )

    assert sum(result["success"] is True for result in results) == 1
    assert all(result["metadata"] == {"command_source": "ai"} for result in results)
    inventories = (
        await service.inventory_for_player(first.id),
        await service.inventory_for_player(second.id),
    )
    assert sorted(item for inventory in inventories for item in inventory) == ["torch"]
