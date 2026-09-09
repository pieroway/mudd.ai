"""Compass directions and movement-relative resolution owned by the engine."""

HORIZONTAL = ("north", "east", "south", "west")
OPPOSITE = {"north": "south", "south": "north", "east": "west", "west": "east",
            "up": "down", "down": "up"}
RELATIVE = {"forward": 0, "right": 1, "backwards": 2, "backward": 2, "left": -1}
DIRECTIONS = {**{key: key for key in OPPOSITE}, **{key[0]: key for key in OPPOSITE},
              **{key: key for key in RELATIVE}}


def resolve_direction(direction: str, facing: str) -> str:
    normalized = DIRECTIONS.get(direction, direction)
    if normalized in RELATIVE:
        return HORIZONTAL[(HORIZONTAL.index(facing) + RELATIVE[normalized]) % 4]
    return normalized
