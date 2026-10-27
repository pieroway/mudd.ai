"""Engine-owned building topology decorated with strictly validated AI content."""

from typing import Any

from pydantic import Field

from app.ai.neighborhood import (
    BuildingDraft,
    DraftModel,
    NeighborhoodDraft,
    NeighborhoodRequest,
    ObjectDraft,
    RoomDraft,
    validate_budget,
)


class BuildingContent(DraftModel):
    """Provider content has no authority over exits or floor assignments."""

    buildings: list[BuildingDraft] = Field(min_length=1, max_length=1)
    rooms: list[RoomDraft] = Field(min_length=1, max_length=24)
    objects: list[ObjectDraft] = Field(max_length=24)


def building_layout(request: NeighborhoodRequest) -> list[dict[str, Any]]:
    if not request.floors:
        raise ValueError("Building mode requires floors")
    slots: list[dict[str, Any]] = []
    for level in range(-request.basement_levels, request.floors):
        count = (
            1 if level < 0 else request.rooms_per_floor + (request.main_rooms if level == 0 else 0)
        )
        for index in range(count):
            purpose = "room"
            if level < 0:
                purpose = "cellar" if level == -1 else "lower basement chamber"
            elif level == 0 and index >= request.rooms_per_floor:
                purpose = "additional main-floor room from the theme"
            elif index == 0:
                purpose = "entrance" if level == 0 else "stair landing room"
            slots.append({"key": f"room_{len(slots) + 1}", "level": level, "purpose": purpose})
    return slots


def assemble_building(content: BuildingContent, request: NeighborhoodRequest) -> NeighborhoodDraft:
    """Connect each floor and adjacent levels without adding rooms to the budget."""
    slots = building_layout(request)
    rooms = {room.key: room for room in content.rooms}
    if len(rooms) != len(content.rooms) or set(rooms) != {slot["key"] for slot in slots}:
        raise ValueError("Building rooms must match the engine's room slots")
    building = content.buildings[0]
    if any(room.building != building.key for room in content.rooms):
        raise ValueError("Building mode requires exactly one building and no outdoor rooms")
    levels: dict[int, list[str]] = {}
    for slot in slots:
        levels.setdefault(slot["level"], []).append(slot["key"])
    # Keep the entrance's reverse direction free, including west-facing entrances.
    horizontal = "north" if request.direction == "west" else "east"
    connections: list[dict[str, Any]] = [
        {
            "source": "anchor",
            "direction": request.direction,
            "destination": levels[0][0],
            "door": {
                "name": "entrance door",
                "description": "A sturdy door guards the building entrance.",
            },
        }
    ]
    for members in levels.values():
        for source, destination in zip(members, members[1:]):
            connections.append(
                {
                    "source": source,
                    "direction": horizontal,
                    "destination": destination,
                    "door": None,
                }
            )
    for level in range(-request.basement_levels, request.floors - 1):
        connections.append(
            {
                "source": levels[level][0],
                "direction": "up",
                "destination": levels[level + 1][0],
                "door": (
                    {"name": "cellar hatch", "description": "A heavy hatch covers the stairs."}
                    if level < 0
                    else None
                ),
            }
        )
    draft = NeighborhoodDraft.model_validate(
        {
            "buildings": [building.model_dump()],
            "rooms": [rooms[slot["key"]].model_dump() for slot in slots],
            "connections": connections,
            "objects": [obj.model_dump() for obj in content.objects],
        }
    )
    validate_budget(draft, request)
    return draft
