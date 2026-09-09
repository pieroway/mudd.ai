import asyncio

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select

from app.ai.fake import FakeAIProvider
from app.ai.provider import AIProviderError
from app.ai.world import RoomProposalContent, WorldGenerationRequest, sentence_count
from app.commands.parser import parse_command
from app.db.seed import seed_world
from app.models import ExitRecord, RoomRecord, WorldProposalRecord
from app.repositories.world_proposals import WorldProposalRepository
from app.services.ai_preferences import set_admin
from app.services.ai_usage import usage_status
from app.services.auth import register_account
from app.services.game import GameService


async def connect(factory, provider=None, **kwargs):
    identity = await register_account("Builder", "Password1!")
    await set_admin(factory, "Builder", True)
    provider = provider or FakeAIProvider()
    game = GameService(factory, world_provider=provider, ai_provider=provider,
                       narration_enabled=True, **kwargs)
    await game.connect_player("admin", "Builder", player_id=identity.player_id)
    await game.execute("admin", "north")
    return game, provider, identity


async def command(game, identity, text):
    return await game.execute("admin", text, account_id=identity.account_id)


async def propose(game, identity):
    reply = await command(game, identity, "/world propose n A Quiet Clearing")
    assert reply["success"], reply
    return reply["proposal_id"]


async def counts(factory):
    async with factory() as session:
        return tuple([await session.scalar(select(func.count()).select_from(model))
                      for model in (RoomRecord, ExitRecord, WorldProposalRecord)])


@pytest.mark.parametrize("text,number", [
    ('Dr. Moss watches. A bell rings! "Who goes there?" Nobody answers. Silence.', 5),
    ('A 1.5 metre stone. Moss, e.g. green moss, covers it.', 2),
    ('Wind... Silence?! A final fragment', 3), ('One。Two！Three？', 3),
])
def test_sentence_convention(text, number):
    assert sentence_count(text) == number


@pytest.mark.parametrize("fields", [
    {"name": ""}, {"name": "x" * 101}, {"description": "x" * 2001},
    {"description": "One. Two. Three. Four. Five. Six."}, {"description": "\x1b[31mRed"},
    {"description": "..."}, {"exits": {"north": "vault"}}, {"name": 12},
])
def test_invalid_content(fields):
    with pytest.raises(ValidationError):
        RoomProposalContent.model_validate({"name": "Clearing", "description": "Still air.", **fields})


def test_parser_preserves_brief_and_context_bounds():
    assert parse_command('/WORLD propose N A Quiet "Clearing"')['arguments'] == [
        'propose', 'n', 'A Quiet "Clearing"']
    with pytest.raises(ValidationError):
        WorldGenerationRequest(brief="Hi", source_name="Forest", source_description="界" * 3000,
                               direction="north", return_direction="south")


async def test_draft_approval_persistence_and_multiplayer(session_factory):
    game, provider, identity = await connect(session_factory)
    bob = await register_account("Bob", "Password1!")
    await game.connect_player("bob", "Bob", player_id=bob.player_id)
    await game.execute("bob", "north")
    proposal_id = await propose(game, identity)
    assert await counts(session_factory) == (5, 8, 1)
    assert not (await game.execute("bob", "north"))["success"]
    assert not provider.requests and not provider.narration_requests
    assert (await usage_status(session_factory, identity.account_id, 50))["used"] == 1
    context = provider.world_requests[0].model_dump()
    assert set(context) == {"brief", "source_name", "source_description", "direction", "return_direction"}
    assert context["brief"] == "A Quiet Clearing"
    for secret in (identity.account_id, identity.player_id, "Builder", "Edric", "inventory"):
        assert secret not in str(context)
    restarted = GameService(session_factory, world_provider=provider)
    await restarted.connect_player("admin", "Builder", player_id=identity.player_id)
    assert proposal_id in (await command(restarted, identity, "/world proposals"))["output"]
    preview = await command(restarted, identity, f"/world preview {proposal_id}")
    assert "Even the wind seems quieter here." in preview["output"]
    approved = await command(game, identity, f"/world approve {proposal_id}")
    assert approved["success"] and approved["events"][0]["session_id"] == "bob"
    assert "_narration_request" not in approved
    assert await counts(session_factory) == (6, 10, 1)
    assert (await game.execute("bob", "north"))["success"]
    room = await game.room_for_player(bob.player_id)
    assert room.id == approved["room_id"] and sentence_count(room.description) == 5
    assert (await game.execute("bob", "south"))["success"]
    async with session_factory() as session, session.begin():
        await seed_world(session)
    assert await counts(session_factory) == (6, 10, 1)
    repeated = await command(game, identity, f"/world approve {proposal_id}")
    assert repeated["room_id"] == approved["room_id"] and not repeated.get("events")
    assert not (await command(game, identity, f"/world reject {proposal_id}"))["success"]
    assert len(provider.world_requests) == 1


@pytest.mark.parametrize("text", ["/world", "/world propose", "/world propose moon hi",
                                    "/world propose s hi", "/world propose n " + "x" * 401])
async def test_invalid_command_is_free(session_factory, text):
    game, provider, identity = await connect(session_factory)
    assert not (await command(game, identity, text))["success"]
    assert not provider.world_requests
    assert (await usage_status(session_factory, identity.account_id, 50))["used"] == 0


async def test_admin_ownership_disable_reject_and_session(session_factory):
    game, provider, identity = await connect(session_factory)
    proposal_id = await propose(game, identity)
    other = await register_account("Other", "Password1!")
    await game.connect_player("other", "Other", player_id=other.player_id)
    for verb in ("preview", "approve", "reject"):
        text = f"/world {verb} {proposal_id}"
        assert not (await game.execute("other", text, account_id=other.account_id))["success"]
    await set_admin(session_factory, "Other", True)
    assert not (await game.execute("other", f"/world preview {proposal_id}", account_id=other.account_id))["success"]
    assert not (await game.execute("other", f"/world approve {proposal_id}", account_id=identity.account_id))["success"]
    async def denied():
        return False
    assert not (await game.execute("admin", f"/world approve {proposal_id}", account_id=identity.account_id,
                                   authorization_check=denied))["success"]
    await command(game, identity, "south")
    assert not (await command(game, identity, f"/world approve {proposal_id}"))["success"]
    game.world_service.provider = None
    assert not (await command(game, identity, f"/world approve {proposal_id}"))["success"]
    assert (await command(game, identity, f"/world preview {proposal_id}"))["success"]
    assert (await command(game, identity, f"/world reject {proposal_id}"))["success"]
    assert (await command(game, identity, f"/world reject {proposal_id}"))["success"]
    assert await counts(session_factory) == (5, 8, 1)


@pytest.mark.parametrize("change", ["source", "exit", "name"])
async def test_changed_world_marks_draft_stale(session_factory, change):
    game, _, identity = await connect(session_factory)
    proposal_id = await propose(game, identity)
    async with session_factory() as session, session.begin():
        if change == "source":
            (await session.get(RoomRecord, "forest")).description = "Changed."
        elif change == "exit":
            session.add(ExitRecord(room_id="forest", direction="north", destination_room_id="inn"))
        else:
            (await session.get(RoomRecord, "inn")).name = "MOSSY CLEARING"
    reply = await command(game, identity, f"/world approve {proposal_id}")
    assert not reply["success"] and "stale" in reply["output"]
    assert (await counts(session_factory))[0] == 5
    async with session_factory() as session:
        assert (await session.get(WorldProposalRecord, proposal_id)).status == "stale"


async def test_approval_races_and_atomic_failure(session_factory, monkeypatch):
    game, _, identity = await connect(session_factory)
    first = await propose(game, identity)
    second = await propose(game, identity)
    responses = await asyncio.gather(*[command(game, identity, f"/world approve {pid}") for pid in (first, second)])
    assert sum(response["success"] for response in responses) == 1
    assert await counts(session_factory) == (6, 10, 2)


async def test_insert_failure_rolls_back_world(session_factory, monkeypatch):
    game, _, identity = await connect(session_factory)
    proposal_id = await propose(game, identity)
    original = WorldProposalRepository.publish
    async def fail(repo, proposal):
        await original(repo, proposal)
        raise AIProviderError("forced rollback")
    monkeypatch.setattr(WorldProposalRepository, "publish", fail)
    assert not (await command(game, identity, f"/world approve {proposal_id}"))["success"]
    assert await counts(session_factory) == (5, 8, 1)
    async with session_factory() as session:
        assert (await session.get(WorldProposalRecord, proposal_id)).status == "pending"


@pytest.mark.parametrize("failure", ["timeout", "invalid", "error", "move", "revoke", "disconnect"])
async def test_provider_failures_and_changed_authorization(session_factory, failure, caplog):
    class Interrupted(FakeAIProvider):
        async def generate_room(self, request, *, before_dispatch):
            response = await super().generate_room(request, before_dispatch=before_dispatch)
            if failure == "timeout":
                await asyncio.sleep(10)
            if failure == "invalid":
                return {"name": "Gold", "description": "Free gold.", "items": ["gold"]}
            if failure == "error":
                raise RuntimeError("private upstream error")
            if failure == "move":
                await game.execute("admin", "south")
            if failure == "revoke":
                await set_admin(session_factory, "Builder", False)
            if failure == "disconnect":
                await game.disconnect_player("admin")
            return response
    game, _, identity = await connect(
        session_factory, Interrupted(), ai_command_timeout_seconds=1 if failure == "timeout" else 5,
    )
    assert not (await command(game, identity, "/world propose north A clearing"))["success"]
    assert await counts(session_factory) == (5, 8, 0)
    assert (await usage_status(session_factory, identity.account_id, 50))["used"] == 1
    assert "private upstream error" not in caplog.text


async def test_pending_cap_and_daily_allowance(session_factory):
    game, provider, identity = await connect(session_factory)
    for _ in range(9):
        await propose(game, identity)
    replies = await asyncio.gather(*[command(game, identity, "/world propose north A clearing") for _ in range(3)])
    assert sum(reply["success"] for reply in replies) == 1
    assert await counts(session_factory) == (5, 8, 10)
    attempts = len(provider.world_requests)
    assert not (await command(game, identity, "/world propose north A clearing"))["success"]
    assert len(provider.world_requests) == attempts
    game.world_service.daily_request_limit = 0
    async with session_factory() as session, session.begin():
        draft = (await session.scalars(select(WorldProposalRecord))).first()
        draft.status = "rejected"
        draft.decided_at = func.now()
    assert not (await command(game, identity, "/world propose north A clearing"))["success"]
    assert len(provider.world_requests) == attempts


async def test_cross_admin_same_name_and_approve_reject_race(session_factory):
    game, _, identity = await connect(session_factory)
    other = await register_account("OtherAdmin", "Password1!")
    await set_admin(session_factory, "OtherAdmin", True)
    await game.connect_player("other", "OtherAdmin", player_id=other.player_id)
    await game.execute("other", "north")
    first = await propose(game, identity)
    second = await game.execute("other", "/world propose east A clearing", account_id=other.account_id)
    responses = await asyncio.gather(
        command(game, identity, f"/world approve {first}"),
        game.execute("other", f"/world approve {second['proposal_id']}", account_id=other.account_id),
    )
    assert sum(reply["success"] for reply in responses) == 1
    assert await counts(session_factory) == (6, 10, 2)


async def test_approve_reject_race_has_one_terminal_outcome(session_factory):
    game, _, identity = await connect(session_factory)
    proposal_id = await propose(game, identity)
    responses = await asyncio.gather(*[
        command(game, identity, f"/world {verb} {proposal_id}") for verb in ("approve", "reject")])
    assert sum(reply["success"] for reply in responses) == 1
    async with session_factory() as session:
        status = (await session.get(WorldProposalRecord, proposal_id)).status
    assert await counts(session_factory) == ((6, 10, 1) if status == "approved" else (5, 8, 1))


async def test_maximum_description_and_escaped_prose_persist(session_factory):
    prefix = '<script>alert("scene")</script> '
    description = prefix + 'm' * (1999 - len(prefix)) + '.'
    assert len(description) == 2000
    class LongProse(FakeAIProvider):
        async def generate_room(self, request, *, before_dispatch):
            await super().generate_room(request, before_dispatch=before_dispatch)
            return RoomProposalContent(name="Long Glade", description=description)
    game, _, identity = await connect(session_factory, LongProse())
    proposal_id = await propose(game, identity)
    assert description in (await command(game, identity, f"/world preview {proposal_id}"))["output"]
    assert (await command(game, identity, f"/world approve {proposal_id}"))["success"]
    assert description in (await command(game, identity, "north"))["output"]


async def test_admin_edit_persists_notifies_and_invalidates_pending_draft(session_factory):
    game, provider, identity = await connect(session_factory)
    proposal_id = await propose(game, identity)
    bob = await register_account("Bob", "Password1!")
    await game.connect_player("bob", "Bob", player_id=bob.player_id)
    await game.execute("bob", "north")
    description = 'Amber light settles over the moss. The air smells of cedar.'
    reply = await command(game, identity, '/world describe ' + description)
    assert reply["success"] and description in reply["output"]
    assert reply["events"] == [{"session_id": "bob", "text": "This room's description has changed. Use look to read it."}]
    assert "_narration_request" not in reply and len(provider.world_requests) == 1
    assert description in (await game.execute("bob", "look"))["output"]
    async with session_factory() as session, session.begin():
        await seed_world(session)
    assert (await game.room_for_player(identity.player_id)).description == description
    assert "stale" in (await command(game, identity, f"/world approve {proposal_id}"))["output"]
    assert (await usage_status(session_factory, identity.account_id, 50))["used"] == 1
    game.world_service.provider = None
    assert (await command(game, identity, '/world describe Quiet air hangs over the clearing.'))["success"]


@pytest.mark.parametrize("description", ['', 'x' * 2001, 'One. Two. Three. Four. Five. Six.', 'Hi\x1b there'])
async def test_invalid_room_edit_does_not_change_state(session_factory, description):
    game, provider, identity = await connect(session_factory)
    original = (await game.room_for_player(identity.player_id)).description
    assert not (await command(game, identity, '/world describe ' + description))["success"]
    assert (await game.room_for_player(identity.player_id)).description == original
    assert not provider.world_requests


async def test_room_edit_requires_current_admin(session_factory):
    game, _, identity = await connect(session_factory)
    await set_admin(session_factory, "Builder", False)
    assert not (await command(game, identity, '/world describe New prose.'))["success"]
    assert (await game.room_for_player(identity.player_id)).description == 'A dense forest with cool air and rustling leaves.'


async def test_relative_proposal_direction_is_pinned_to_compass(session_factory):
    game, provider, identity = await connect(session_factory)
    proposed = await command(game, identity, '/world propose right A cedar grove')
    assert proposed['success'] and provider.world_requests[-1].direction == 'east'
    assert provider.world_requests[-1].return_direction == 'west'
    approved = await command(game, identity, f"/world approve {proposed['proposal_id']}")
    assert approved['success']
    assert 'You move east.' in (await command(game, identity, 'right'))['output']
