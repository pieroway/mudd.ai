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
    assert "/debug on | off" in result["output"]


def test_lit_carried_torch_reveals_adjacent_room_names():
    world = make_world_with_player()
    player = world["players"]["alan"]
    execute_command(parse_command("take torch"), player, world)

    unlit_result = execute_command(parse_command("look"), player, world)
    execute_command(parse_command("use torch"), player, world)
    lit_result = execute_command(parse_command("look"), player, world)

    assert "Torchlight reaches farther" not in unlit_result["output"]
    assert "Torchlight reaches farther" in lit_result["output"]
    assert "north: Forest" in lit_result["output"]
    assert "south: Docks" in lit_result["output"]


def test_extinguished_torch_no_longer_reveals_adjacent_rooms():
    world = make_world_with_player()
    player = world["players"]["alan"]
    execute_command(parse_command("take torch"), player, world)
    execute_command(parse_command("use torch"), player, world)
    execute_command(parse_command("put out torch"), player, world)

    result = execute_command(parse_command("look"), player, world)

    assert "Torchlight reaches farther" not in result["output"]


def test_successful_movement_consumes_lit_torch_fuel():
    world = make_world_with_player()
    player = world["players"]["alan"]
    execute_command(parse_command("take torch"), player, world)
    execute_command(parse_command("use torch"), player, world)

    execute_command(parse_command("north"), player, world)

    assert world["items"]["torch"].fuel_remaining == 19


def test_failed_movement_does_not_consume_torch_fuel():
    world = make_world_with_player()
    player = world["players"]["alan"]
    execute_command(parse_command("take torch"), player, world)
    execute_command(parse_command("use torch"), player, world)

    execute_command(parse_command("north"), player, world)
    fuel_before_failed_move = world["items"]["torch"].fuel_remaining
    result = execute_command(parse_command("east"), player, world)

    assert result["success"] is False
    assert world["items"]["torch"].fuel_remaining == fuel_before_failed_move


def test_torch_automatically_extinguishes_when_fuel_reaches_zero():
    world = make_world_with_player()
    player = world["players"]["alan"]
    execute_command(parse_command("take torch"), player, world)
    execute_command(parse_command("use torch"), player, world)
    world["items"]["torch"].fuel_remaining = 1

    result = execute_command(parse_command("north"), player, world)

    assert world["items"]["torch"].fuel_remaining == 0
    assert world["items"]["torch"].is_lit is False
    assert "The torch sputters out." in result["output"]
