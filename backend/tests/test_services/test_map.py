from sqlalchemy import select

from app.models.game import PlayerDiscoveryRecord, RoomRecord, ExitRecord
from app.services.game import GameService
from app.services.ai_preferences import set_admin
from tests.test_services.test_world_generation import command, connect
from app.db import get_session_factory


def test_maze_map_requires_live_admin_role_and_lists_unvisited_levels(test_client):
    async def prepare():
        factory = get_session_factory()
        game, _, identity = await connect(factory)
        for line in (
            "/world generate maze --rooms 12 --levels 2 --seed 42 --railways true --loops 100 --secrets 100",
            "open down door", "down",
        ):
            reply = await command(game, identity, line)
            assert reply["success"], reply
        assert len((await game.client_state("admin")).map.rooms) < 12

    assert test_client.get("/auth/maze-map").status_code == 401
    test_client.portal.call(prepare)
    login = test_client.post("/auth/login", json={"username": "Builder", "password": "Password1!"},
                             headers={"Origin": "http://localhost:5173"})
    assert login.status_code == 200
    response = test_client.get("/auth/maze-map")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    data = response.json()
    assert len(data["rooms"]) == 12
    assert {room["z"] for room in data["rooms"]} == {-1, -2}
    assert sum(room["carts"] for room in data["rooms"]) == 1
    assert any(edge["rail"] for edge in data["exits"])
    assert any(edge["hidden"] for edge in data["exits"])
    test_client.portal.call(set_admin, get_session_factory(), "Builder", False)
    assert test_client.get("/auth/maze-map").status_code == 403


async def test_vertical_badges_do_not_reveal_unvisited_destinations(session_factory):
    async with session_factory() as session, session.begin():
        session.add(RoomRecord(id='private_attic', name='Secret Attic', description='A dusty attic.'))
        await session.flush()
        session.add_all([
            ExitRecord(room_id='town_square', direction='up', destination_room_id='private_attic'),
            ExitRecord(room_id='private_attic', direction='down', destination_room_id='town_square'),
        ])
    game = GameService(session_factory)
    await game.connect_player('alice', 'Alice')
    await game.connect_player('bob', 'Bob')
    initial = (await game.client_state('alice')).map
    assert initial.rooms[0].has_up and not initial.rooms[0].has_down
    assert initial.exits == []
    assert 'private_attic' not in initial.model_dump_json()
    assert 'Secret Attic' not in initial.model_dump_json()
    assert (await game.execute('alice', 'up'))['success']
    visited = (await game.client_state('alice')).map
    assert {room.id for room in visited.rooms} == {'town_square', 'private_attic'}
    assert next(room for room in visited.rooms if room.id == 'private_attic').has_down
    assert len(visited.exits) == 2
    assert (await game.client_state('bob')).map == initial


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
