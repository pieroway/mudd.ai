from app.world import create_world
from app.domain.player import Player
from app.commands.parser import parse_command
from app.engine.executor import execute_command


def make_world_with_player():
    world = create_world()
    world["players"]["alan"] = Player(id="alan", name="alan", current_room_id="town_square")
    return world


def test_world_factory_creates_expected_rooms():
    world = make_world_with_player()

    assert set(world["rooms"]) == {"town_square", "forest", "blacksmith", "inn", "docks"}
    assert world["players"]["alan"].current_room_id == "town_square"


def test_player_can_move_north_from_town_square():
    world = make_world_with_player()
    player = world["players"]["alan"]

    result = execute_command(parse_command("north"), player, world)

    assert result["success"] is True
    assert player.current_room_id == "forest"
    assert result["room_id"] == "forest"


def test_look_command_returns_room_description():
    world = make_world_with_player()
    player = world["players"]["alan"]

    result = execute_command(parse_command("look"), player, world)

    assert result["success"] is True
    assert "Town Square" in result["output"]
    assert "marketplace" in result["output"].lower()
    assert "torch" in result["output"]  # Item in room should be listed


def test_help_lists_gameplay_and_client_slash_commands():
    world = make_world_with_player()
    player = world["players"]["alan"]

    result = execute_command(parse_command("help"), player, world)

    assert result["success"] is True
    assert "Available commands: look" in result["output"]
    assert "Slash commands: /theme light | dark | techo" in result["output"]
