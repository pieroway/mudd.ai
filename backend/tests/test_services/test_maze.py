from sqlalchemy import select

from app.models import ExitRecord, RoomRecord
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
