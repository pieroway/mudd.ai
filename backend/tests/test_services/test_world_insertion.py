"""Reviewed route insertion must preserve the existing world."""

import asyncio

import pytest
from sqlalchemy import select

from app.commands.parser import parse_command
from app.models import ExitRecord, ItemRecord, PlayerRecord, RoomRecord, WorldProposalRecord
from app.models.game import DoorRecord
from tests.test_services.test_world_generation import command, connect, counts


def test_insert_parser_preserves_theme():
    assert parse_command('/world insert N --theme "North Street"')["arguments"] == [
        "insert",
        'N --theme "North Street"',
    ]


async def draft(factory):
    game, provider, identity = await connect(factory)
    await command(game, identity, "south")
    response = await command(game, identity, '/world insert north --theme "North Street"')
    assert response["success"], response
    return game, provider, identity, response


async def test_insertion_preview_approval_and_repeat(session_factory):
    before = await counts(session_factory)
    game, provider, identity, response = await draft(session_factory)
    assert "Before:" in response["output"] and "After:" in response["output"]
    assert await counts(session_factory) == (before[0], before[1], before[2] + 1)
    proposal_id = response["proposal_id"]
    async with session_factory() as session:
        proposal = await session.get(WorldProposalRecord, proposal_id)
        source_id = proposal.source_room_id
        forest_id = proposal.payload["destination_id"]
    approved = await command(game, identity, f"/world approve {proposal_id}")
    assert approved["success"], approved
    new_id = approved["room_id"]
    async with session_factory() as session:
        edges = {
            (e.room_id, e.direction): e.destination_room_id
            for e in (await session.scalars(select(ExitRecord))).all()
        }
        assert edges[source_id, "north"] == new_id
        assert edges[new_id, "south"] == source_id
        assert edges[new_id, "north"] == forest_id
        assert edges[forest_id, "south"] == new_id
        assert (await session.get(RoomRecord, forest_id)).name == "Forest"
    assert await counts(session_factory) == (before[0] + 1, before[1] + 2, before[2] + 1)
    assert (await command(game, identity, f"/world approve {proposal_id}"))["room_id"] == new_id
    assert len(provider.world_requests) == 1
    assert (await command(game, identity, "north"))["success"]
    assert (await command(game, identity, "north"))["success"]


@pytest.mark.parametrize("change", ["description", "return_exit"])
async def test_destination_changes_make_insertion_stale(session_factory, change):
    game, _, identity, response = await draft(session_factory)
    async with session_factory() as session, session.begin():
        proposal = await session.get(WorldProposalRecord, response["proposal_id"])
        destination = await session.get(RoomRecord, proposal.payload["destination_id"])
        if change == "description":
            destination.description = "The forest changed."
        else:
            edge = await session.get(ExitRecord, (destination.id, "south"))
            await session.delete(edge)
    before = await counts(session_factory)
    reply = await command(game, identity, f'/world approve {response["proposal_id"]}')
    assert not reply["success"] and "stale" in reply["output"].lower()
    assert await counts(session_factory) == before


async def test_unused_exit_is_rejected_without_ai(session_factory):
    game, provider, identity = await connect(session_factory)
    reply = await command(game, identity, '/world insert north --theme "North Street"')
    assert not reply["success"]
    assert not provider.world_requests


async def test_rejected_insertion_preserves_route(session_factory):
    game, _, identity, response = await draft(session_factory)
    before = await counts(session_factory)
    assert (await command(game, identity, f'/world reject {response["proposal_id"]}'))["success"]
    assert not (await command(game, identity, f'/world approve {response["proposal_id"]}'))[
        "success"
    ]
    assert await counts(session_factory) == before


@pytest.mark.parametrize(
    "arguments",
    [
        "",
        'north --theme ""',
        'north --theme "unterminated',
        "north --rooms 2",
        'north --theme "street" --extra',
        'up --theme "street"',
        'north --theme "' + "x" * 401 + '"',
    ],
)
async def test_invalid_insertion_is_free(session_factory, arguments):
    game, provider, identity = await connect(session_factory)
    await command(game, identity, "south")
    reply = await command(game, identity, "/world insert " + arguments)
    assert not reply["success"]
    assert not provider.world_requests


async def test_door_route_is_rejected_before_billing(session_factory):
    game, provider, identity = await connect(session_factory)
    await command(game, identity, "south")
    async with session_factory() as session, session.begin():
        player = await session.get(PlayerRecord, identity.player_id)
        edge = await session.get(ExitRecord, (player.current_room_id, "north"))
        session.add(
            DoorRecord(
                id="insertion_door",
                name="gate",
                description="A gate.",
                room_id=player.current_room_id,
                destination_room_id=edge.destination_room_id,
            )
        )
        await session.flush()
        edge.door_id = "insertion_door"
    reply = await command(game, identity, '/world insert north --theme "street"')
    assert not reply["success"] and "doors" in reply["output"]
    assert not provider.world_requests


async def test_insertion_preserves_items_and_players(session_factory):
    game, _, identity, response = await draft(session_factory)
    async with session_factory() as session, session.begin():
        proposal = await session.get(WorldProposalRecord, response["proposal_id"])
        forest_id = proposal.payload["destination_id"]
        session.add(
            ItemRecord(
                id="forest_relic",
                name="relic",
                description="An old relic.",
                room_id=forest_id,
                portable=True,
            )
        )
    async with session_factory() as session:
        before = [
            (p.id, p.current_room_id) for p in (await session.scalars(select(PlayerRecord))).all()
        ]
    reply = await command(game, identity, f'/world approve {response["proposal_id"]}')
    assert reply["success"], reply
    async with session_factory() as session:
        assert (await session.get(ItemRecord, "forest_relic")).room_id == forest_id
        assert [
            (p.id, p.current_room_id) for p in (await session.scalars(select(PlayerRecord))).all()
        ] == before


async def test_mid_publication_failure_rolls_back_route(session_factory, monkeypatch):
    from sqlalchemy.exc import IntegrityError
    from sqlalchemy.ext.asyncio import AsyncSession

    game, _, identity, response = await draft(session_factory)
    before = await counts(session_factory)
    original = AsyncSession.flush
    calls = 0

    async def fail_second_flush(self, *args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise IntegrityError("injected conflict", {}, Exception("conflict"))
        return await original(self, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(AsyncSession, "flush", fail_second_flush)
        reply = await command(game, identity, f'/world approve {response["proposal_id"]}')
    assert not reply["success"] and "conflict" in reply["output"].lower()
    assert await counts(session_factory) == before
    async with session_factory() as session:
        proposal = await session.get(WorldProposalRecord, response["proposal_id"])
        assert proposal.status == "pending"
        edge = await session.get(ExitRecord, (proposal.source_room_id, "north"))
        assert edge.destination_room_id == proposal.payload["destination_id"]


async def test_tampered_insertion_payload_cannot_publish(session_factory):
    game, _, identity, response = await draft(session_factory)
    async with session_factory() as session, session.begin():
        proposal = await session.get(WorldProposalRecord, response["proposal_id"])
        proposal.payload = {**proposal.payload, "extra_exit": "secret"}
    before = await counts(session_factory)
    reply = await command(game, identity, f'/world approve {response["proposal_id"]}')
    assert not reply["success"]
    assert await counts(session_factory) == before


async def test_competing_drafts_only_publish_once(session_factory):
    game, _, identity, first = await draft(session_factory)
    second = await command(game, identity, '/world insert north --theme "another street"')
    assert second["success"], second
    before = await counts(session_factory)
    replies = await asyncio.gather(
        *[
            command(game, identity, f'/world approve {response["proposal_id"]}')
            for response in (first, second)
        ]
    )
    assert sum(reply["success"] for reply in replies) == 1
    assert any("stale" in reply["output"] for reply in replies)
    assert await counts(session_factory) == (before[0] + 1, before[1] + 2, before[2])


async def test_route_change_during_generation_discards_draft(session_factory):
    game, provider, identity = await connect(session_factory)
    await command(game, identity, "south")
    original = provider.generate_room

    async def change_route(request, **kwargs):
        content = await original(request, **kwargs)
        async with session_factory() as session, session.begin():
            forest = await session.scalar(select(RoomRecord).where(RoomRecord.name == "Forest"))
            forest.description = "Changed while generating."
        return content

    provider.generate_room = change_route
    before = await counts(session_factory)
    reply = await command(game, identity, '/world insert north --theme "North Street"')
    assert not reply["success"] and "changed" in reply["output"]
    assert await counts(session_factory) == before


async def test_insertion_requires_creator_at_source(session_factory):
    game, _, identity, response = await draft(session_factory)
    await command(game, identity, "north")
    before = await counts(session_factory)
    reply = await command(game, identity, f'/world approve {response["proposal_id"]}')
    assert not reply["success"] and "Return" in reply["output"]
    assert await counts(session_factory) == before
