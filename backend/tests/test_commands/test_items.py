import pytest

from app.commands.parser import parse_command
from app.domain.player import Player
from app.engine.executor import execute_command
from app.world import create_world


@pytest.fixture
def world_and_player():
    world = create_world()
    player = Player(id="alan", name="Alan", current_room_id="town_square")
    world["players"][player.id] = player
    return world, player


@pytest.mark.parametrize(
    ("raw", "action", "target"),
    [
        ("get torch", "take", "torch"),
        ("take torch", "take", "torch"),
        ("drop torch", "drop", "torch"),
        ("examine torch", "examine", "torch"),
        ("inspect torch", "examine", "torch"),
        ("open chest", "open", "chest"),
        ("close chest", "close", "chest"),
        ("use torch", "use", "torch"),
    ],
)
def test_item_commands_are_parsed_with_aliases(raw, action, target):
    command = parse_command(raw)

    assert command["action"] == action
    assert command["target"] == target


@pytest.mark.parametrize("verb", ["take", "get"])
def test_take_from_container_command_is_parsed(verb):
    command = parse_command(f"{verb} torch from chest")

    assert command["action"] == "take_from"
    assert command["target"] == "torch"
    assert command["container"] == "chest"


@pytest.mark.parametrize("preposition", ["in", "into"])
def test_put_in_container_command_is_parsed(preposition):
    command = parse_command(f"put torch {preposition} chest")

    assert command["action"] == "put"
    assert command["target"] == "torch"
    assert command["container"] == "chest"


def test_look_in_container_command_is_parsed():
    command = parse_command("look in chest")

    assert command["action"] == "look_in"
    assert command["container"] == "chest"


def test_player_can_take_item_from_current_room(world_and_player):
    world, player = world_and_player

    result = execute_command(parse_command("take torch"), player, world)

    assert result["success"] is True
    assert result["output"] == "You take the torch."
    assert player.inventory == ["torch"]
    assert world["items"]["torch"].owned_by == player.id
    assert world["items"]["torch"].room_id is None


def test_player_cannot_take_item_from_another_room(world_and_player):
    world, player = world_and_player

    result = execute_command(parse_command("take sword"), player, world)

    assert result["success"] is False
    assert result["output"] == "You do not see a sword here."
    assert player.inventory == []


def test_player_can_drop_carried_item(world_and_player):
    world, player = world_and_player
    execute_command(parse_command("take torch"), player, world)

    result = execute_command(parse_command("drop torch"), player, world)

    assert result["success"] is True
    assert result["output"] == "You drop the torch."
    assert player.inventory == []
    assert world["items"]["torch"].owned_by is None
    assert world["items"]["torch"].room_id == "town_square"


def test_player_cannot_drop_item_they_do_not_carry(world_and_player):
    world, player = world_and_player

    result = execute_command(parse_command("drop torch"), player, world)

    assert result["success"] is False
    assert result["output"] == "You are not carrying a torch."


def test_player_can_examine_room_item_or_carried_item(world_and_player):
    world, player = world_and_player

    room_result = execute_command(parse_command("inspect torch"), player, world)
    execute_command(parse_command("take torch"), player, world)
    inventory_result = execute_command(parse_command("examine torch"), player, world)

    assert room_result == {"success": True, "output": "A flickering torch."}
    assert inventory_result == {"success": True, "output": "A flickering torch."}


@pytest.mark.parametrize(
    ("raw", "output"),
    [
        ("take", "Take what?"),
        ("drop", "Drop what?"),
        ("examine", "Examine what?"),
        ("open", "Open what?"),
        ("close", "Close what?"),
        ("use", "Use what?"),
    ],
)
def test_item_commands_require_a_target(world_and_player, raw, output):
    world, player = world_and_player

    result = execute_command(parse_command(raw), player, world)

    assert result == {"success": False, "output": output}


def test_player_can_open_and_close_an_openable_item(world_and_player):
    world, player = world_and_player

    opened = execute_command(parse_command("open chest"), player, world)
    opened_again = execute_command(parse_command("open chest"), player, world)
    closed = execute_command(parse_command("close chest"), player, world)

    assert opened == {"success": True, "output": "You open the chest."}
    assert opened_again == {"success": False, "output": "The chest is already open."}
    assert closed == {"success": True, "output": "You close the chest."}
    assert world["items"]["chest"].is_open is False


def test_player_cannot_open_an_item_without_that_capability(world_and_player):
    world, player = world_and_player

    result = execute_command(parse_command("open torch"), player, world)

    assert result == {"success": False, "output": "The torch cannot be opened."}


def test_player_must_carry_an_item_to_use_it(world_and_player):
    world, player = world_and_player

    not_carried = execute_command(parse_command("use torch"), player, world)
    execute_command(parse_command("take torch"), player, world)
    used = execute_command(parse_command("use torch"), player, world)

    assert not_carried == {
        "success": False,
        "output": "You need to be carrying the torch to use it.",
    }
    assert used == {"success": True, "output": "The torch casts a steady pool of light."}


def test_player_can_put_an_item_in_an_open_container_and_take_it_back(world_and_player):
    world, player = world_and_player
    execute_command(parse_command("take torch"), player, world)
    execute_command(parse_command("open chest"), player, world)

    put_result = execute_command(parse_command("put torch in chest"), player, world)
    take_result = execute_command(parse_command("take torch from chest"), player, world)

    assert put_result == {"success": True, "output": "You put the torch in the chest."}
    assert take_result == {"success": True, "output": "You take the torch from the chest."}
    assert player.inventory == ["torch"]
    assert world["items"]["torch"].owned_by == player.id
    assert world["items"]["torch"].container_id is None


def test_player_can_look_in_an_open_container(world_and_player):
    world, player = world_and_player
    execute_command(parse_command("take torch"), player, world)
    execute_command(parse_command("open chest"), player, world)
    execute_command(parse_command("put torch in chest"), player, world)

    result = execute_command(parse_command("look in chest"), player, world)

    assert result == {"success": True, "output": "The chest contains: torch."}


def test_empty_and_closed_container_descriptions(world_and_player):
    world, player = world_and_player

    closed_result = execute_command(parse_command("look in chest"), player, world)
    execute_command(parse_command("open chest"), player, world)
    empty_result = execute_command(parse_command("look in chest"), player, world)

    assert closed_result == {"success": False, "output": "The chest is closed."}
    assert empty_result == {"success": True, "output": "The chest is empty."}


def test_player_cannot_use_a_closed_container(world_and_player):
    world, player = world_and_player
    execute_command(parse_command("take torch"), player, world)

    result = execute_command(parse_command("put torch in chest"), player, world)

    assert result == {"success": False, "output": "The chest is closed."}
    assert player.inventory == ["torch"]


def test_player_can_only_put_carried_items_in_containers(world_and_player):
    world, player = world_and_player
    execute_command(parse_command("open chest"), player, world)

    result = execute_command(parse_command("put torch in chest"), player, world)

    assert result == {"success": False, "output": "You are not carrying a torch."}
