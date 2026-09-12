import asyncio
from copy import deepcopy

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select

from app.ai.fake import FakeAIProvider
from app.ai.neighborhood import NeighborhoodDraft
from app.ai.provider import AIFailureReason, AIProviderFailure, AIProviderError
from app.commands.parser import parse_command
from app.models import ExitRecord, ItemRecord, RoomRecord, WorldProposalRecord
from app.models.game import BuildingRecord, DoorRecord
from app.repositories.game import GameRepository
from app.services.ai_preferences import set_admin
from app.services.ai_usage import usage_status
from app.services.auth import register_account
from app.services.game import GameService
from tests.test_services.test_world_generation import command, connect


async def generate(game, identity, options='north --rooms 2 --buildings 1'):
    reply = await command(game, identity, '/world generate ' + options)
    assert reply['success'], reply
    return reply['proposal_id']


async def canonical_counts(factory):
    async with factory() as session:
        return tuple([await session.scalar(select(func.count()).select_from(model))
                      for model in (RoomRecord, ExitRecord, BuildingRecord, DoorRecord, ItemRecord)])


async def test_publish_explore_doors_containers_and_restart(session_factory):
    game, provider, identity = await connect(session_factory)
    before = await canonical_counts(session_factory)
    proposal_id = await generate(game, identity)
    assert await canonical_counts(session_factory) == before
    assert not (await command(game, identity, 'north'))['success']
    preview = await command(game, identity, f'/world preview {proposal_id}')
    for text in ['Cedar Lane', 'Cedar Workroom', 'cedar door', 'stone bench', 'wooden box', 'clay cup', 'closed']:
        assert text in preview['output']
    assert len(provider.neighborhood_requests) == 1
    assert not provider.world_requests and not provider.narration_requests
    assert (await usage_status(session_factory, identity.account_id, 50))['used'] == 1
    context = provider.neighborhood_requests[0].model_dump_json()
    assert identity.account_id not in context and identity.player_id not in context
    approved = await command(game, identity, f'/world approve {proposal_id}')
    assert approved['success'], approved
    assert await canonical_counts(session_factory) == tuple(a + b for a, b in zip(before, (2, 4, 1, 1, 3)))
    async with session_factory() as session:
        state = await GameRepository(session).map_state(identity.player_id)
        assert approved['room_id'] not in {r.id for r in state.rooms}
    assert (await command(game, identity, 'north'))['success']
    assert not (await command(game, identity, 'take stone bench'))['success']
    assert not (await command(game, identity, 'north'))['success']
    assert (await command(game, identity, 'open north door'))['success']
    assert (await command(game, identity, 'north'))['success']
    assert not (await command(game, identity, 'take clay cup from wooden box'))['success']
    assert (await command(game, identity, 'open wooden box'))['success']
    assert (await command(game, identity, 'take clay cup from wooden box'))['success']
    assert not (await command(game, identity, 'take wooden box'))['success']
    assert (await command(game, identity, 'close south door'))['success']
    restarted = GameService(session_factory, world_provider=provider)
    await restarted.connect_player('admin', 'Builder', player_id=identity.player_id)
    assert not (await command(restarted, identity, 'south'))['success']
    assert 'clay cup' in (await command(restarted, identity, 'inventory'))['output']
    repeated = await command(restarted, identity, f'/world approve {proposal_id}')
    assert repeated['success'] and repeated['room_id'] == approved['room_id']


@pytest.mark.parametrize('options', ['--radius 3', '--rooms 0', '--buildings 5', '--rooms nope',
                                    '--unknown 2', '--theme "unterminated', '--rooms 2 --rooms 3',
                                    'south', '--theme ' + 'x' * 401])
async def test_invalid_options_are_free(session_factory, options):
    game, provider, identity = await connect(session_factory)
    assert not (await command(game, identity, '/world generate ' + options))['success']
    assert not provider.neighborhood_requests
    assert (await usage_status(session_factory, identity.account_id, 50))['used'] == 0


async def test_around_finds_outdoor_frontier_and_approves_at_origin(session_factory):
    game, provider, identity = await connect(session_factory)
    await command(game, identity, 'south')
    assert not (await command(game, identity, '/world generate around --radius 0'))['success']
    proposal_id = await generate(game, identity, 'around --radius 1 --rooms 1 --buildings 0 --theme "Quiet Corner"')
    assert provider.neighborhood_requests[0].origin_name == 'Town Square'
    assert provider.neighborhood_requests[0].anchor_name == 'Forest'
    assert provider.neighborhood_requests[0].brief == 'Quiet Corner'
    assert (await command(game, identity, f'/world approve {proposal_id}'))['success']


@pytest.mark.parametrize('change', ['source', 'origin', 'name'])
async def test_stale_approval_is_atomic(session_factory, change):
    game, _, identity = await connect(session_factory)
    await command(game, identity, 'south')
    proposal_id = await generate(game, identity, 'around')
    async with session_factory() as session, session.begin():
        if change == 'name':
            session.add(RoomRecord(id='conflict', name='CEDAR LANE', description='Still air.'))
        else:
            room = await session.get(RoomRecord, 'forest' if change == 'source' else 'town_square')
            room.description = 'Changed.'
    before = await canonical_counts(session_factory)
    assert not (await command(game, identity, f'/world approve {proposal_id}'))['success']
    assert await canonical_counts(session_factory) == before
    async with session_factory() as session:
        assert (await session.get(WorldProposalRecord, proposal_id)).status == 'stale'


async def test_ownership_rejection_disable_and_allowance(session_factory):
    game, provider, identity = await connect(session_factory)
    proposal_id = await generate(game, identity)
    other = await register_account('OtherBuilder', 'Password1!')
    await set_admin(session_factory, 'OtherBuilder', True)
    await game.connect_player('other', 'OtherBuilder', player_id=other.player_id)
    for verb in ['preview', 'approve', 'reject']:
        assert not (await game.execute('other', f'/world {verb} {proposal_id}', account_id=other.account_id))['success']
    game.world_service.provider = None
    assert not (await command(game, identity, f'/world approve {proposal_id}'))['success']
    assert (await command(game, identity, f'/world preview {proposal_id}'))['success']
    assert (await command(game, identity, f'/world reject {proposal_id}'))['success']
    game.world_service.provider = provider
    game.world_service.daily_request_limit = 1
    assert not (await command(game, identity, '/world generate'))['success']
    assert len(provider.neighborhood_requests) == 1


async def test_concurrent_approval_publishes_once(session_factory):
    game, _, identity = await connect(session_factory)
    proposal_id = await generate(game, identity)
    before = await canonical_counts(session_factory)
    replies = await asyncio.gather(*[command(game, identity, f'/world approve {proposal_id}') for _ in range(2)])
    assert all(r['success'] for r in replies)
    assert replies[0]['room_id'] == replies[1]['room_id']
    assert await canonical_counts(session_factory) == tuple(a + b for a, b in zip(before, (2, 4, 1, 1, 3)))


async def test_provider_wait_has_no_world_lock_and_moving_discards_draft(session_factory):
    started, resume = asyncio.Event(), asyncio.Event()
    class Waiting(FakeAIProvider):
        async def generate_neighborhood(self, request, *, before_dispatch):
            draft = await super().generate_neighborhood(request, before_dispatch=before_dispatch)
            started.set()
            await resume.wait()
            return draft
    game, _, identity = await connect(session_factory, Waiting())
    pending = asyncio.create_task(command(game, identity, '/world generate'))
    await asyncio.wait_for(started.wait(), 2)
    try:
        assert (await asyncio.wait_for(command(game, identity, 'south'), 2))['success']
    finally:
        resume.set()
    assert not (await pending)['success']
    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(WorldProposalRecord)) == 0


@pytest.mark.parametrize('corruption', ['disconnected', 'direction', 'building', 'object', 'extra', 'sentences'])
async def test_invalid_provider_draft_never_publishes(session_factory, corruption):
    class Invalid(FakeAIProvider):
        async def generate_neighborhood(self, request, *, before_dispatch):
            draft = (await super().generate_neighborhood(request, before_dispatch=before_dispatch)).model_dump()
            if corruption == 'disconnected':
                draft['connections'].pop()
            elif corruption == 'direction':
                draft['connections'][0]['direction'] = 'east'
            elif corruption == 'building':
                draft['connections'][1]['door'] = None
            elif corruption == 'object':
                draft['objects'][2]['container'] = 'cup'
            elif corruption == 'extra':
                draft['currency'] = 1000
            else:
                draft['rooms'][0]['description'] = 'One. Two. Three. Four.'
            return draft
    game, _, identity = await connect(session_factory, Invalid())
    before = await canonical_counts(session_factory)
    assert not (await command(game, identity, '/world generate north'))['success']
    assert await canonical_counts(session_factory) == before


async def test_stored_draft_revalidated_and_no_partial_inserts(session_factory):
    game, _, identity = await connect(session_factory)
    proposal_id = await generate(game, identity)
    async with session_factory() as session, session.begin():
        proposal = await session.get(WorldProposalRecord, proposal_id)
        payload = deepcopy(proposal.payload)
        payload['content']['connections'][1]['door'] = None
        proposal.payload = payload
    before = await canonical_counts(session_factory)
    assert not (await command(game, identity, f'/world approve {proposal_id}'))['success']
    assert await canonical_counts(session_factory) == before


async def test_gameplay_snapshot_blocks_publication_until_commit(session_factory):
    game, _, identity = await connect(session_factory)
    proposal_id = await generate(game, identity)
    other = await register_account('Walker', 'Password1!')
    async with session_factory() as session, session.begin():
        repo = GameRepository(session)
        player_record = await repo.load_player_for_update(other.player_id)
        world, player = await repo.load_world(player_record, lock_items=True)
        pending = asyncio.create_task(command(game, identity, f'/world approve {proposal_id}'))
        try:
            with pytest.raises(TimeoutError):
                await asyncio.wait_for(asyncio.shield(pending), 0.15)
            await repo.persist_world(world, player, player_record, persist_items=True)
        except BaseException:
            pending.cancel()
            raise
    assert (await asyncio.wait_for(pending, 3))['success']


async def test_generation_timeout_and_revoked_admin_never_store_draft(session_factory):
    class Timeout(FakeAIProvider):
        async def generate_neighborhood(self, request, *, before_dispatch):
            await super().generate_neighborhood(request, before_dispatch=before_dispatch)
            await asyncio.sleep(1)
    game, _, identity = await connect(session_factory, Timeout())
    game.world_service.neighborhood_timeout_seconds = 0.05
    assert not (await command(game, identity, '/world generate'))['success']
    class Revoked(FakeAIProvider):
        async def generate_neighborhood(self, request, *, before_dispatch):
            draft = await super().generate_neighborhood(request, before_dispatch=before_dispatch)
            await set_admin(session_factory, 'Builder', False)
            return draft
    game.world_service.provider = Revoked()
    game.world_service.neighborhood_timeout_seconds = 5
    assert not (await command(game, identity, '/world generate'))['success']
    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(WorldProposalRecord)) == 0


def test_parser_preserves_generation_options():
    assert parse_command('/WORLD GENERATE north --theme "Quiet Corner"')['arguments'] == [
        'generate', 'north --theme "Quiet Corner"']


def test_schema_rejects_empty_and_extra_fields():
    with pytest.raises(ValidationError):
        NeighborhoodDraft.model_validate({'buildings': [], 'rooms': [], 'connections': [], 'objects': []})


@pytest.mark.parametrize('reason', list(AIFailureReason))
async def test_failure_reason_reaches_player_and_safe_logs(session_factory, caplog, reason):
    class Failure(FakeAIProvider):
        async def generate_neighborhood(self, request, *, before_dispatch):
            raise AIProviderFailure(reason, http_status=400 if reason == AIFailureReason.API_REQUEST else None,
                                    detail='PRIVATE-SECRET-NOT-ALLOWED')
    game, _, identity = await connect(session_factory, Failure())
    before = await canonical_counts(session_factory)
    reply = await command(game, identity, '/world generate north --theme "PRIVATE-SECRET-NOT-ALLOWED"')
    assert not reply['success']
    assert f'[{reason.value}]' in reply['output']
    assert 'No world changes were made.' in reply['output']
    if reason == AIFailureReason.API_REQUEST:
        assert 'HTTP 400' in reply['output']
    if reason == AIFailureReason.TIMEOUT:
        assert '60 seconds' in reply['output']
    assert f'reason={reason.value}' in caplog.text and 'elapsed_ms=' in caplog.text
    assert 'PRIVATE-SECRET-NOT-ALLOWED' not in reply['output'] + caplog.text
    assert identity.account_id not in caplog.text and identity.player_id not in caplog.text
    assert all(record.exc_info is None for record in caplog.records if record.name == 'app.services.neighborhood')
    assert await canonical_counts(session_factory) == before


@pytest.mark.parametrize('error,reason', [(RuntimeError('PRIVATE-EXCEPTION'), 'internal_error'),
                                        (AIProviderError('PRIVATE-EXCEPTION'), 'provider_unavailable'),
                                        (TimeoutError('PRIVATE-EXCEPTION'), 'timeout')])
async def test_unclassified_exceptions_are_sanitized(session_factory, caplog, error, reason):
    class Failure(FakeAIProvider):
        async def generate_neighborhood(self, request, *, before_dispatch):
            raise error
    game, _, identity = await connect(session_factory, Failure())
    reply = await command(game, identity, '/world generate north')
    assert f'[{reason}]' in reply['output']
    assert 'PRIVATE-EXCEPTION' not in reply['output'] + caplog.text


async def test_exhausted_account_is_distinct_from_provider_limits(session_factory, caplog):
    game, provider, identity = await connect(session_factory, ai_daily_request_limit=0)
    reply = await command(game, identity, '/world generate north')
    assert '[account_allowance]' in reply['output'] and '00:00 UTC' in reply['output']
    assert not provider.neighborhood_requests
    assert 'reason=account_allowance' in caplog.text
