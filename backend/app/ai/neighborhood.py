"""Strict, bounded neighborhood drafts. References are local labels, never world IDs."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from app.ai.world import plain_text, sentence_count
from app.domain.directions import OPPOSITE


class DraftModel(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, frozen=True, str_strip_whitespace=True)


class NamedDraft(DraftModel):
    key: str = Field(pattern=r'^[a-z][a-z0-9_]{0,31}$')
    name: str = Field(min_length=1, max_length=100)

    @field_validator('name')
    @classmethod
    def clean_name(cls, value):
        return plain_text(value)


class BuildingDraft(NamedDraft):
    pass


class RoomDraft(NamedDraft):
    description: str = Field(min_length=1, max_length=1000)
    building: str | None

    @field_validator('description')
    @classmethod
    def short_room(cls, value):
        if not 1 <= sentence_count(value) <= 3:
            raise ValueError('Rooms allow at most three sentences')
        return plain_text(value)


class ObjectDraft(NamedDraft):
    description: str = Field(min_length=1, max_length=240)
    kind: Literal['fixture', 'portable', 'container']
    room: str | None
    container: str | None

    @field_validator('description')
    @classmethod
    def short_object(cls, value):
        if sentence_count(value) != 1:
            raise ValueError('Objects allow one sentence')
        return plain_text(value)


class DoorDraft(DraftModel):
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1, max_length=240)

    @field_validator('name', 'description')
    @classmethod
    def clean(cls, value):
        return plain_text(value)

    @field_validator('description')
    @classmethod
    def short_door(cls, value):
        if sentence_count(value) != 1:
            raise ValueError('Doors allow one sentence')
        return value


class ConnectionDraft(DraftModel):
    source: str
    direction: Literal['north', 'south', 'east', 'west']
    destination: str
    door: DoorDraft | None


class NeighborhoodDraft(DraftModel):
    buildings: list[BuildingDraft] = Field(max_length=4)
    rooms: list[RoomDraft] = Field(min_length=1, max_length=12)
    connections: list[ConnectionDraft] = Field(min_length=1, max_length=20)
    objects: list[ObjectDraft] = Field(max_length=24)

    @model_validator(mode='after')
    def coherent(self):
        rooms = {room.key: room for room in self.rooms}
        buildings = {building.key for building in self.buildings}
        objects = {obj.key: obj for obj in self.objects}
        if (len(rooms) != len(self.rooms) or 'anchor' in rooms or len(buildings) != len(self.buildings)
                or len(objects) != len(self.objects)):
            raise ValueError('Duplicate or reserved labels')
        if len({room.name.casefold() for room in self.rooms}) != len(rooms):
            raise ValueError('Room names must be distinct')
        if any(room.building is not None and room.building not in buildings for room in self.rooms):
            raise ValueError('Unknown building')
        adjacency: dict[str, set[str]] = {key: set() for key in [*rooms, 'anchor']}
        slots: set[tuple[str, str]] = set()
        for edge in self.connections:
            if edge.source not in adjacency or edge.destination not in rooms or edge.source == edge.destination:
                raise ValueError('Connections may only join draft rooms or the anchor')
            for slot in [(edge.source, edge.direction), (edge.destination, OPPOSITE[edge.direction])]:
                if slot in slots:
                    raise ValueError('Conflicting exit directions')
                slots.add(slot)
            adjacency[edge.source].add(edge.destination)
            adjacency[edge.destination].add(edge.source)
            source_building = rooms[edge.source].building if edge.source in rooms else None
            if source_building != rooms[edge.destination].building and edge.door is None:
                raise ValueError('Building entrances require doors')
        if len(adjacency['anchor']) != 1 or sum(edge.source == 'anchor' for edge in self.connections) != 1:
            raise ValueError('Exactly one attachment to the existing world is required')

        def reachable(start: str, allowed: set[str]) -> set[str]:
            seen = {start}
            queue = [start]
            for key in queue:
                for neighbor in sorted(adjacency[key] & allowed - seen):
                    seen.add(neighbor)
                    queue.append(neighbor)
            return seen

        if reachable('anchor', set(adjacency)) != set(adjacency):
            raise ValueError('Every room must be reachable from the anchor')
        for building in buildings:
            members = {room.key for room in self.rooms if room.building == building}
            if not 1 <= len(members) <= 3 or reachable(min(members), members) != members:
                raise ValueError('Buildings require one to three internally connected rooms')
        per_room: dict[str, list[str]] = {key: [] for key in rooms}
        for obj in self.objects:
            if (obj.room is None) == (obj.container is None):
                raise ValueError('Objects require exactly one location')
            room_key = obj.room
            if obj.container is not None:
                parent = objects.get(obj.container)
                if parent is None or parent.kind != 'container' or parent.room is None or obj.kind != 'portable':
                    raise ValueError('Only portable objects may be placed in a room container')
                room_key = parent.room
            if room_key not in rooms:
                raise ValueError('Unknown object room')
            per_room[room_key].append(obj.name.casefold())
        if any(len(names) > 4 or len(set(names)) != len(names) for names in per_room.values()):
            raise ValueError('At most four distinctly named objects per room')
        return self


class NeighborhoodRequest(DraftModel):
    brief: str = Field(min_length=1, max_length=400)
    origin_name: str
    anchor_name: str
    anchor_description: str
    direction: Literal['north', 'south', 'east', 'west']
    max_rooms: int = Field(ge=1, le=12)
    max_buildings: int = Field(ge=0, le=4)

    @model_validator(mode='after')
    def bounded(self):
        plain_text(self.brief)
        if len(self.model_dump_json().encode('utf-8')) > 8192:
            raise ValueError('Context too large')
        return self


def validate_budget(draft: NeighborhoodDraft, request: NeighborhoodRequest) -> None:
    if len(draft.rooms) > request.max_rooms or len(draft.buildings) > request.max_buildings:
        raise ValueError('Draft exceeds requested budget')
    if next(edge.direction for edge in draft.connections if edge.source == 'anchor') != request.direction:
        raise ValueError('Draft attachment direction does not match')


def draft_failure(error: ValueError):
    """Classify validation without exposing input values, field names, or exception text."""
    from pydantic import ValidationError
    from app.ai.provider import AIFailureReason, AIProviderFailure, SAFE_DRAFT_DETAILS

    messages = [str(error)] if not isinstance(error, ValidationError) else [
        issue['msg'].removeprefix('Value error, ')
        for issue in error.errors(include_input=False, include_context=False, include_url=False)
    ]
    detail = next((message for message in messages if message in SAFE_DRAFT_DETAILS), None)
    return AIProviderFailure(AIFailureReason.INVALID_DRAFT, detail=detail)
