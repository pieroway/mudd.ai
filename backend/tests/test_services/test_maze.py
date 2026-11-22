from sqlalchemy import select

import asyncio

from app.domain.directions import OPPOSITE
from app.domain.catalogue import CATALOGUE
from app.domain.door import Door
from app.domain.item import Item
from app.domain.player import Player
from app.domain.room import Room
from app.engine.rail import CART, SWITCH, execute_rail
from app.models import ExitRecord, ItemRecord, RoomRecord
from app.models.game import DoorRecord, PlayerRecord
from app.repositories.game import GameRepository
from app.services.ai_preferences import set_admin
from app.services.auth import register_account
from app.services.maze import MazeConfig, railway, topology
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


def test_rail_network_is_connected_reciprocal_and_bounded():
    config = MazeConfig(seed=7421, railways=True, rail_density=50)
    cells, passages = topology(config)
    rails = railway(config, cells, passages)
    assert len(rails) == 126
    assert any(len(routes) > 2 for routes in rails.values())
    seen = {cells[0]}
    frontier = [cells[0]]
    links = {(first, direction): second for first, direction, second in passages}
    links.update({(second, OPPOSITE[direction]): first for first, direction, second in passages})
    for first in frontier:
        for direction in rails[first]:
            second = links[first, direction]
            assert OPPOSITE[direction] in rails[second]
            if second not in seen:
                seen.add(second)
                frontier.append(second)
    assert seen == set(rails)


def test_rail_switch_and_slope_rules():
    routes = {"east": "east", "west": "west", "up": "upper"}
    junction = Room("junction", "Junction", "", exits=routes, conditions={"rail": list(routes)})
    rooms = {"junction": junction}
    for direction, destination in routes.items():
        reverse = OPPOSITE[direction]
        rooms[destination] = Room(destination, destination, "", exits={reverse: "junction"},
                                  conditions={"rail": [reverse]})
    switch = Item.from_template("switch", CATALOGUE[SWITCH], room_id=junction.id)
    switch.state["alignment"] = "west"
    cart = Item.from_template("cart", CATALOGUE[CART], room_id=junction.id)
    player = Player(id="rider", name="Rider", current_room_id=junction.id)
    world = {"rooms": rooms, "items": {switch.id: switch, cart.id: cart}}
    cart.state["braked"] = False
    reply = execute_rail(["push", "east"], player, world)
    assert not reply["success"] and "aligned" in reply["output"]
    assert execute_rail(["switch", "east"], player, world)["success"]
    junction.doors["east"] = Door("gate", "gate", "", "junction", "east")
    reply = execute_rail(["push", "east"], player, world)
    assert not reply["success"] and "closed door" in reply["output"]
    assert execute_rail(["switch", "up"], player, world)["success"]
    cart.relationships["occupants"] = [player.id]
    player.state["occupied_item"] = cart.id
    reply = execute_rail(["ride", "up"], player, world)
    assert not reply["success"] and "uphill" in reply["output"]
    cart.relationships["occupants"] = []
    player.state.pop("occupied_item")
    assert execute_rail(["pull", "up"], player, world)["success"]
    assert player.current_room_id == cart.room_id == "upper"


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


async def test_shared_minecart_moves_rider_and_cargo_atomically(session_factory):
    game, _, identity = await connect(session_factory)
    reply = await command(game, identity, "/world generate maze --rooms 9 --levels 1 "
                          "--seed 7421 --railways true --minecarts true --rail-density 100")
    assert reply["success"], reply
    for line in ("open down door", "down"):
        assert (await command(game, identity, line))["success"]
    other = await register_account("RailRider", "Password1!")
    async with session_factory() as session, session.begin():
        cart = (await session.scalars(select(ItemRecord).where(ItemRecord.template_id == "vehicle_minecart"))).one()
        cart_id, station = cart.id, cart.room_id
        room = await session.get(RoomRecord, station)
        direction = room.conditions["rail"][0]
        link = await session.get(ExitRecord, (station, direction))
        destination = link.destination_room_id
        other_player = await session.get(PlayerRecord, other.player_id)
        other_player.current_room_id = station
        session.add(ItemRecord(id="rail-test-cargo", name="test cargo", description="A bundle of cargo.",
                               room_id=station, portable=True))
    await game.connect_player("other", "RailRider", player_id=other.player_id)

    async def issue(actor, line):
        key = "admin" if actor == identity else "other"
        return await game.execute(key, line, account_id=actor.account_id)

    riders = (identity, other)
    boarding = await asyncio.gather(*(issue(actor, "board minecart") for actor in riders))
    assert sum(reply["success"] for reply in boarding) == 1
    rider, observer = riders if boarding[0]["success"] else riders[::-1]
    assert not (await issue(observer, "/rail brake off"))["success"]
    assert "brake" in (await issue(rider, f"/rail ride {direction}"))["output"]
    for line in ("take test cargo", "put test cargo in minecart", "/rail brake off",
                 f"/rail ride {direction}"):
        reply = await issue(rider, line)
        assert reply["success"], (line, reply)
    async with session_factory() as session:
        cart = await session.get(ItemRecord, cart_id)
        cargo = await session.get(ItemRecord, "rail-test-cargo")
        player = await session.get(PlayerRecord, rider.player_id)
        other_player = await session.get(PlayerRecord, observer.player_id)
        assert cart.room_id == player.current_room_id == destination
        assert cart.relationships["occupants"] == [rider.player_id]
        assert cargo.container_id == cart.id
        assert other_player.current_room_id == station
    assert (await issue(rider, "take test cargo from minecart"))["success"]
    assert (await issue(rider, "leave minecart"))["success"]
