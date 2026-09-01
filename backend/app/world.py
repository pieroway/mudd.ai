from __future__ import annotations

from typing import Any

from app.domain.item import Item
from app.domain.room import Room


def create_world() -> dict[str, Any]:
    """Create the deterministic shared world used by the game service."""
    rooms = {
        "town_square": Room(
            id="town_square",
            name="Town Square",
            description="A bustling marketplace at the heart of the town.",
        ),
        "forest": Room(
            id="forest",
            name="Forest",
            description="A dense forest with cool air and rustling leaves.",
        ),
        "blacksmith": Room(
            id="blacksmith",
            name="Blacksmith",
            description="A warm forge with sparks flying from the anvil.",
        ),
        "inn": Room(
            id="inn",
            name="Inn",
            description="A cozy inn with lanterns and a soft wood fire.",
        ),
        "docks": Room(
            id="docks",
            name="Docks",
            description="A weathered dock overlooking the harbor.",
        ),
    }

    rooms["town_square"].exits = {
        "north": "forest",
        "south": "docks",
        "east": "inn",
        "west": "blacksmith",
    }
    rooms["forest"].exits = {"south": "town_square"}
    rooms["blacksmith"].exits = {"east": "town_square"}
    rooms["inn"].exits = {"west": "town_square"}
    rooms["docks"].exits = {"north": "town_square"}

    items = {
        "torch": Item(
            id="torch",
            name="torch",
            description="A flickering torch.",
            room_id="town_square",
        ),
        "mushroom": Item(
            id="mushroom",
            name="mushroom",
            description="A small forest mushroom.",
            room_id="forest",
        ),
        "sword": Item(
            id="sword",
            name="sword",
            description="A sturdy iron sword.",
            room_id="blacksmith",
        ),
        "key": Item(
            id="key",
            name="key",
            description="A brass key.",
            room_id="inn",
        ),
    }

    return {"rooms": rooms, "items": items, "players": {}}

