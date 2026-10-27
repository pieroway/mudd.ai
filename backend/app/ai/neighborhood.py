"""Strict, bounded neighborhood drafts. References are local labels, never world IDs."""
import re
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
    interaction_target: str | None
    template_id: str | None = None
    locked: bool = False
    key_room: str | None = None
    hiding_place: str | None = None

    @model_validator(mode='after')
    def registered_template(self):
        from app.domain.catalogue import CATALOGUE
        if self.template_id is not None:
            if self.template_id not in CATALOGUE:
                raise ValueError('Generated objects must use registered templates')
            template = CATALOGUE[self.template_id]
            if self.kind == 'portable' and not template.physical.portable:
                raise ValueError('Large objects cannot be generated as portable items')
            if self.kind == 'container' and 'container' not in template.capabilities:
                raise ValueError('Container objects require container templates')
            if self.locked and 'lockable' not in template.capabilities:
                raise ValueError('Generated locks require lockable templates')
        elif self.locked or self.key_room or self.hiding_place:
            raise ValueError('Generated locks require registered templates')
        return self

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
    direction: Literal['north', 'south', 'east', 'west', 'up', 'down']
    destination: str
    door: DoorDraft | None


class NeighborhoodDraft(DraftModel):
    buildings: list[BuildingDraft] = Field(max_length=4)
    rooms: list[RoomDraft] = Field(min_length=1, max_length=24)
    connections: list[ConnectionDraft] = Field(min_length=1, max_length=48)
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
            if not members or reachable(min(members), members) != members:
                raise ValueError('Buildings require internally connected rooms')
        per_room: dict[str, list[str]] = {key: [] for key in rooms}
        for obj in self.objects:
            if obj.interaction_target is not None and (obj.kind != 'portable' or obj.interaction_target not in objects or obj.interaction_target == obj.key):
                raise ValueError('Usable items require another draft object target')
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
        if any(obj.template_id for obj in self.objects):
            materialize_objects(self)
        return self


class NeighborhoodRequest(DraftModel):
    brief: str = Field(min_length=1, max_length=2000)
    origin_name: str
    anchor_name: str
    anchor_description: str
    direction: Literal['north', 'south', 'east', 'west', 'up', 'down']
    max_rooms: int = Field(ge=1, le=24)
    max_buildings: int = Field(ge=0, le=4)
    floors: int = Field(default=0, ge=0, le=5)
    rooms_per_floor: int = Field(default=4, ge=1, le=8)
    main_rooms: int = Field(default=0, ge=0, le=8)
    basement_levels: int = Field(default=0, ge=0, le=3)

    @model_validator(mode='after')
    def bounded(self):
        plain_text(self.brief)
        if self.floors:
            total = self.floors * self.rooms_per_floor + self.main_rooms + self.basement_levels
            if total != self.max_rooms or self.max_buildings != 1 or self.direction in {'up', 'down'}:
                raise ValueError('Invalid building room budget or entrance')
        elif self.max_rooms > 12 or self.main_rooms or self.basement_levels:
            raise ValueError('Use building mode for larger drafts')
        if len(self.model_dump_json().encode('utf-8')) > 8192:
            raise ValueError('Context too large')
        return self


def validate_budget(draft: NeighborhoodDraft, request: NeighborhoodRequest) -> None:
    if len(draft.rooms) > request.max_rooms or len(draft.buildings) > request.max_buildings:
        raise ValueError('Draft exceeds requested budget')
    if next(edge.direction for edge in draft.connections if edge.source == 'anchor') != request.direction:
        raise ValueError('Draft attachment direction does not match')
    if request.floors:
        if len(draft.buildings) != 1 or any(room.building != draft.buildings[0].key for room in draft.rooms):
            raise ValueError('Building mode requires exactly one building and no outdoor rooms')
        levels = building_levels(draft)
        expected = {floor: request.rooms_per_floor + (request.main_rooms if floor == 0 else 0)
                    for floor in range(request.floors)}
        expected.update({-level: 1 for level in range(1, request.basement_levels + 1)})
        actual = {level: list(levels.values()).count(level) for level in set(levels.values())}
        if actual != expected:
            raise ValueError('Building floor counts do not match the request')
        # Each floor must be connected without detouring through another floor.
        for level in expected:
            members = {key for key, value in levels.items() if value == level}
            seen = {min(members)}
            for _ in members:
                for edge in draft.connections:
                    if edge.source in members and edge.destination in members:
                        if edge.source in seen or edge.destination in seen:
                            seen.update((edge.source, edge.destination))
            if seen != members:
                raise ValueError('Each floor must be internally connected')
    elif any(sum(room.building == building.key for room in draft.rooms) > 3 for building in draft.buildings):
        raise ValueError('Buildings require one to three internally connected rooms')


def building_levels(draft: NeighborhoodDraft) -> dict[str, int]:
    """Derive floors from authoritative exit directions; reject contradictory stairs."""
    entrance = next(edge.destination for edge in draft.connections if edge.source == 'anchor')
    levels = {entrance: 0}
    adjacency: dict[str, list[tuple[str, int]]] = {room.key: [] for room in draft.rooms}
    for edge in draft.connections:
        if edge.source == 'anchor':
            continue
        delta = 1 if edge.direction == 'up' else -1 if edge.direction == 'down' else 0
        adjacency[edge.source].append((edge.destination, delta))
        adjacency[edge.destination].append((edge.source, -delta))
    queue = [entrance]
    for key in queue:
        for neighbor, delta in adjacency[key]:
            level = levels[key] + delta
            if neighbor in levels:
                if levels[neighbor] != level:
                    raise ValueError('Building stairs assign conflicting floors')
            else:
                levels[neighbor] = level
                queue.append(neighbor)
    if len(levels) != len(draft.rooms):
        raise ValueError('Building rooms must connect internally')
    return levels


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


def _one_sentence(value: object) -> str | None:
    """Keep the first plain-text sentence from model prose, if it is usable."""
    if not isinstance(value, str):
        return None
    try:
        value = plain_text(value).strip()
    except ValueError:
        return None
    if not value:
        return None
    parts = [part.strip() for part in re.split(r'''[.!?…。！？]+["'”’»]*''', value) if part.strip()]
    return parts[0] if parts else None


def normalize_topology(payload: object, request: NeighborhoodRequest) -> NeighborhoodDraft | None:
    """Build safe geography around usable provider prose."""
    if request.floors:
        return None  # Never replace a requested multi-floor building with a flat chain.
    raw_objects = payload.get('objects') if isinstance(payload, dict) else None
    if isinstance(raw_objects, list) and any(isinstance(obj, dict) and (obj.get('template_id') or obj.get('locked')) for obj in raw_objects):
        return None  # Never discard lock/key constraints while repairing prose.
    if (not isinstance(payload, dict) or set(payload) != {'buildings', 'rooms', 'connections', 'objects'}
            or not isinstance(payload.get('rooms'), list)):
        return None
    rooms: list[dict[str, object]] = []
    names: set[str] = set()
    for raw in payload['rooms']:
        if not isinstance(raw, dict) or len(rooms) >= request.max_rooms:
            continue
        name, description = raw.get('name'), _one_sentence(raw.get('description'))
        if not isinstance(name, str) or description is None:
            continue
        try:
            name = plain_text(name).strip()
        except ValueError:
            continue
        if not name or name.casefold() in names:
            continue
        rooms.append({'key': f'room_{len(rooms) + 1}', 'name': name, 'description': description, 'building': None})
        names.add(name.casefold())
    if not rooms:
        return None
    buildings: list[dict[str, str]] = []
    raw_buildings = payload.get('buildings')
    if isinstance(raw_buildings, list):
        for raw in raw_buildings:
            if not isinstance(raw, dict) or len(buildings) >= min(request.max_buildings, len(rooms)):
                continue
            name = raw.get('name')
            if not isinstance(name, str) or not name.strip():
                continue
            try:
                name = plain_text(name).strip()
            except ValueError:
                continue
            if any(name.casefold() == item['name'].casefold() for item in buildings):
                continue
            buildings.append({'key': f'building_{len(buildings) + 1}', 'name': name})
    for offset, building in enumerate(buildings, start=1):
        rooms[-offset]['building'] = building['key']
    doors: list[dict[str, str]] = []
    raw_connections = payload.get('connections')
    if isinstance(raw_connections, list):
        for raw in raw_connections:
            if not isinstance(raw, dict) or not isinstance(raw.get('door'), dict):
                continue
            name, description = raw['door'].get('name'), _one_sentence(raw['door'].get('description'))
            if not isinstance(name, str) or description is None:
                continue
            try:
                name = plain_text(name).strip()
            except ValueError:
                continue
            if name:
                doors.append({'name': name, 'description': description})
    connections: list[dict[str, object]] = []
    previous, previous_building = 'anchor', None
    for room in rooms:
        room_key, building_key = room['key'], room['building']
        assert isinstance(room_key, str) and (building_key is None or isinstance(building_key, str))
        door = None
        if previous_building != building_key:
            door = doors.pop(0) if doors else {'name': 'sturdy door', 'description': 'A sturdy door marks the threshold'}
        connections.append({'source': previous, 'direction': request.direction, 'destination': room_key, 'door': door})
        previous, previous_building = room_key, building_key
    objects: list[dict[str, object]] = []
    per_room = {room['key']: 0 for room in rooms}
    raw_objects = payload.get('objects')
    if isinstance(raw_objects, list):
        for raw in raw_objects:
            if not isinstance(raw, dict) or len(objects) >= 24:
                continue
            name, kind, description = raw.get('name'), raw.get('kind'), _one_sentence(raw.get('description'))
            if not isinstance(name, str) or kind not in {'fixture', 'portable', 'container'} or description is None:
                continue
            try:
                name = plain_text(name).strip()
            except ValueError:
                continue
            target = next((key for key, count in per_room.items() if count < 4), None)
            if not name or target is None:
                continue
            objects.append({'key': f'object_{len(objects) + 1}', 'name': name, 'description': description, 'kind': kind, 'room': target, 'container': None, 'interaction_target': None})
            per_room[target] += 1
    try:
        return NeighborhoodDraft.model_validate({'buildings': buildings, 'rooms': rooms, 'connections': connections, 'objects': objects})
    except ValueError:
        return None


def materialize_objects(draft, room_ids=None, object_ids=None):
    """Translate reviewed data into instances and prove all generated locks solvable."""
    from app.domain.catalogue import CATALOGUE
    from app.domain.item import Item
    from app.domain.room import Room
    from app.domain.item_context import root
    from app.domain.item_dependencies import provision_lock, validate_dependencies

    room_ids = room_ids or {key: key for key in ['anchor', *(room.key for room in draft.rooms)]}
    object_ids = object_ids or {obj.key: obj.key for obj in draft.objects}
    rooms = {room_ids[room.key]: Room(room_ids[room.key], room.name, room.description) for room in draft.rooms}
    rooms[room_ids['anchor']] = Room(room_ids['anchor'], 'Existing entrance', 'The existing world is nearby.')
    for edge in draft.connections:
        source, destination = room_ids[edge.source], room_ids[edge.destination]
        rooms[source].exits[edge.direction] = destination
        rooms[destination].exits[OPPOSITE[edge.direction]] = source
    items = {}
    for obj in draft.objects:
        locations = {'room_id': room_ids.get(obj.room), 'container_id': object_ids.get(obj.container)}
        if obj.template_id:
            item = Item.from_template(object_ids[obj.key], CATALOGUE[obj.template_id], **locations,
                provenance={'source': 'ai_generated', 'generation_reason': 'reviewed_world_proposal'})
            item.name, item.description = obj.name, obj.description
        else:
            item = Item(id=object_ids[obj.key], name=obj.name, description=obj.description,
                portable=obj.kind == 'portable', can_open=obj.kind == 'container',
                provenance={'source': 'ai_generated', 'generation_reason': 'reviewed_world_proposal'}, **locations)
        item.interaction_target_id = object_ids.get(obj.interaction_target)
        items[item.id] = item
    for obj in draft.objects:
        if obj.locked:
            if obj.key_room is not None and obj.key_room not in room_ids:
                raise ValueError('Generated key placement must reference a draft room')
            if obj.hiding_place is not None and obj.hiding_place not in object_ids:
                raise ValueError('Generated hiding place must reference a draft object')
            item = items[object_ids[obj.key]]
            origin = root(item, items)
            if origin is None or origin.room_id is None:
                raise ValueError('Generated lock must have a valid room')
            provision_lock(item, items, rooms, origin.room_id,
                key_room=room_ids.get(obj.key_room) if obj.key_room else None,
                hiding_place=object_ids.get(obj.hiding_place), source='ai_generated')
    if len(items) > 24:
        raise ValueError('Generated keys exceed the object budget')
    per_room = {}
    for item in items.values():
        origin = root(item, items)
        if origin:
            per_room.setdefault(origin.room_id, []).append(item.name.casefold())
    if any(len(names) > 4 or len(names) != len(set(names)) for names in per_room.values()):
        raise ValueError('Generated keys exceed per-room limits or duplicate object names')
    validate_dependencies(items, rooms, room_ids['anchor'])
    return items
