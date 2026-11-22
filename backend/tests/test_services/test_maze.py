from sqlalchemy import select

from app.models import ExitRecord, RoomRecord
from app.models.game import DoorRecord, PlayerRecord
from app.repositories.game import GameRepository
from app.services.ai_preferences import set_admin
from app.services.maze import MazeConfig, topology
from tests.test_services.test_world_generation import command, connect


def test_large_maze_topology_is_deterministic_and_connected():
    config = MazeConfig(seed=7421)
    cells, passages = topology(config)
    assert (cells, passages) == topology(config)
    assert len(set(cells)) == 250
    assert len({cell[2] for cell in cells}) == 5
    neighbors = {cell: set() for cell in cells}
    for source, _, target in passages:
        assert sum(abs(first - second) for first, second in zip(source, target)) == 1
        neighbors[source].add(target)
        neighbors[target].add(source)
    frontier = [cells[0]]
    visited = {cells[0]}
    for cell in frontier:
        for neighbor in neighbors[cell] - visited:
            visited.add(neighbor)
            frontier.append(neighbor)
    assert visited == set(cells)


async def test_maze_command_publishes_reciprocal_exits_and_rejects_collision(session_factory):
    game, _, identity = await connect(session_factory)
    line = "/world generate maze --rooms 250 --levels 5 --seed 7421"
    reply = await command(game, identity, line)
    assert reply["success"], reply
    reply = await command(game, identity, line)
    assert not reply["success"] and "already has an exit" in reply["output"]
    await set_admin(session_factory, "Builder", False)
    reply = await command(game, identity, line)
    assert not reply["success"] and "requires admin" in reply["output"]
    async with session_factory() as session:
        rooms = list(await session.scalars(select(RoomRecord)))
        generated = {room.id for room in rooms if "maze" in room.conditions}
        assert len(generated) == 250
        exits = list(await session.scalars(select(ExitRecord)))
        index = {(edge.room_id, edge.destination_room_id): edge for edge in exits}
        trapdoors = []
        for edge in exits:
            if edge.room_id in generated or edge.destination_room_id in generated:
                reverse = index[edge.destination_room_id, edge.room_id]
                assert edge.door_id == reverse.door_id
                if edge.door_id:
                    trapdoors.append(edge)
        assert trapdoors


async def test_maze_secret_door_discovery_and_tools_persist(session_factory):
    game, _, identity = await connect(session_factory)
    reply = await command(game, identity, "/world generate maze --rooms 9 --levels 1 "
                          "--seed 7421 --loops 100 --secrets 100 --locks 100 --jams 100")
    assert reply["success"], reply
    for line in ("open down door", "down", "take mine passage key", "take iron crowbar"):
        reply = await command(game, identity, line)
        assert reply["success"], reply
    async with session_factory() as session, session.begin():
        door = (await session.scalars(select(DoorRecord).where(DoorRecord.is_hidden))).first()
        assert door is not None
        door_id = door.id
        edges = (await session.scalars(select(ExitRecord).where(ExitRecord.door_id == door_id))).all()
        edge, opposite = edges
        direction, reverse = edge.direction, opposite.direction
        player = await session.get(PlayerRecord, identity.player_id)
        player.current_room_id = edge.room_id
        repository = GameRepository(session)
        for room_id in (edge.room_id, opposite.room_id):
            await repository.discover_room(player.id, room_id)
        assert not any(link.room_id == edge.room_id and link.direction == direction
                       for link in (await repository.map_state(player.id)).exits)
    assert not (await command(game, identity, direction))["success"]
    assert "concealed" in (await command(game, identity, "search"))["output"]
    assert not (await command(game, identity, f"open {direction} door"))["success"]
    for line in (
        f"unlock {direction} door with mine passage key",
        f"pry {direction} door with iron crowbar",
        f"open {direction} door",
        direction,
        f"close {reverse} door",
    ):
        reply = await command(game, identity, line)
        assert reply["success"], (line, reply)
    async with session_factory() as session:
        door = await session.get(DoorRecord, door_id)
        assert not (door.is_open or door.is_hidden or door.is_locked or door.is_jammed)
        assert any(link.room_id == edge.room_id and link.direction == direction
                   for link in (await GameRepository(session).map_state(identity.player_id)).exits)
