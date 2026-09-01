from ..fixtures.world import seed_world
from app.commands.parser import parse_command
from app.engine.executor import execute_command


def test_seed_world_fixture_creates_expected_rooms():
    world = seed_world()

    assert set(world["rooms"]) == {"town_square", "forest", "blacksmith", "inn", "docks"}
    assert world["players"]["alan"].current_room_id == "town_square"


def test_player_can_move_north_from_town_square():
    world = seed_world()
    player = world["players"]["alan"]

    result = execute_command(parse_command("north"), player, world)

    assert result["success"] is True
    assert player.current_room_id == "forest"
    assert result["room_id"] == "forest"


def test_look_command_returns_room_description():
    world = seed_world()
    player = world["players"]["alan"]

    result = execute_command(parse_command("look"), player, world)

    assert result["success"] is True
    assert "Town Square" in result["output"]
    assert "marketplace" in result["output"].lower()
