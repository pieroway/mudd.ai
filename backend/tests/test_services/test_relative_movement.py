import pytest

from app.ai.fake import FakeAIProvider
from app.commands.parser import parse_command
from app.domain.directions import resolve_direction
from app.models import ExitRecord, PlayerRecord, RoomRecord
from app.services.game import GameService


@pytest.mark.parametrize('facing,expected', [
    ('north', ['west', 'east', 'north', 'south']),
    ('east', ['north', 'south', 'east', 'west']),
    ('south', ['east', 'west', 'south', 'north']),
    ('west', ['south', 'north', 'west', 'east']),
])
def test_relative_direction_mapping(facing, expected):
    assert [resolve_direction(word, facing) for word in ('left', 'right', 'forward', 'backwards')] == expected


@pytest.mark.parametrize('word', ['left', 'right', 'forward', 'backward', 'backwards', 'up', 'u', 'down', 'd'])
def test_new_directions_are_classic_commands(word):
    assert parse_command(word.upper())['action'] == 'move'


async def test_heading_persists_and_failed_moves_do_not_turn(session_factory):
    provider = FakeAIProvider()
    game = GameService(session_factory, ai_provider=provider)
    player = await game.connect_player('one', 'Walker')
    assert 'Facing: north.' in (await game.execute('one', 'look'))['output']
    assert 'You move west.' in (await game.execute('one', 'left'))['output']
    assert not (await game.execute('one', 'forward'))['success']
    assert 'Facing: west.' in (await game.execute('one', 'look'))['output']
    assert 'You move east.' in (await game.execute('one', 'backwards'))['output']
    await game.disconnect_player('one')
    restarted = GameService(session_factory, ai_provider=provider)
    await restarted.connect_player('two', 'Walker', player_id=player.id)
    assert 'Facing: east.' in (await restarted.execute('two', 'look'))['output']
    assert 'You move south.' in (await restarted.execute('two', 'right'))['output']
    assert 'You move north.' in (await restarted.execute('two', 'backwards'))['output']
    assert 'You move north.' in (await restarted.execute('two', 'forward'))['output']
    assert provider.requests == []


async def test_vertical_moves_preserve_heading_and_events_use_compass(session_factory):
    game = GameService(session_factory)
    alice = await game.connect_player('alice', 'Alice')
    bob = await game.connect_player('bob', 'Bob')
    moved = await game.execute('alice', 'right')
    assert moved['events'] == [{'session_id': 'bob', 'text': 'Alice leaves to the east.'}]
    async with session_factory() as session, session.begin():
        session.add(RoomRecord(id='loft', name='Loft', description='Dust settles on warm beams.'))
        await session.flush()
        session.add_all([ExitRecord(room_id='inn', direction='up', destination_room_id='loft'),
                         ExitRecord(room_id='loft', direction='down', destination_room_id='inn')])
    assert 'You move up.' in (await game.execute('alice', 'up'))['output']
    assert 'Facing: east.' in (await game.execute('alice', 'look'))['output']
    assert 'You move down.' in (await game.execute('alice', 'd'))['output']
    async with session_factory() as session:
        assert (await session.get(PlayerRecord, alice.id)).facing_direction == 'east'
        assert (await session.get(PlayerRecord, bob.id)).facing_direction == 'north'
