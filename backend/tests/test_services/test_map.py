from sqlalchemy import select

from app.models.game import PlayerDiscoveryRecord
from app.services.game import GameService


async def test_discovery_is_private_persistent_and_failed_moves_do_not_reveal_rooms(session_factory):
    game = GameService(session_factory)
    alice = await game.connect_player('alice', 'Alice')
    await game.connect_player('bob', 'Bob')
    initial = (await game.client_state('alice')).map
    assert [(room.id, room.name) for room in initial.rooms] == [('town_square', 'Town Square')]
    assert initial.exits == []
    assert (await game.execute('alice', 'north'))['success']
    visited = (await game.client_state('alice')).map
    assert {room.id for room in visited.rooms} == {'town_square', 'forest'}
    assert {(edge.room_id, edge.direction, edge.destination_room_id) for edge in visited.exits} == {
        ('town_square', 'north', 'forest'), ('forest', 'south', 'town_square'),
    }
    assert not (await game.execute('alice', 'north'))['success']
    assert (await game.client_state('alice')).map == visited
    assert (await game.client_state('bob')).map == initial
    await game.disconnect_player('alice')
    restarted = GameService(session_factory)
    await restarted.connect_player('again', 'Alice', player_id=alice.id)
    assert (await restarted.client_state('again')).map == visited
    assert (await restarted.client_state('again')).room_id == 'forest'
    await restarted.execute('again', 'south')
    await restarted.execute('again', 'north')
    async with session_factory() as session:
        discoveries = (await session.scalars(select(PlayerDiscoveryRecord).where(
            PlayerDiscoveryRecord.player_id == alice.id))).all()
    assert len(discoveries) == 2
