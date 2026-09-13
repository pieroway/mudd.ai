"""Explicit, player-visible data for optional client panels."""

from pydantic import BaseModel, ConfigDict


class InventoryEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    id: str
    name: str


class MapRoom(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    id: str
    name: str
    building_id: str | None
    has_up: bool = False
    has_down: bool = False


class MapExit(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    room_id: str
    direction: str
    destination_room_id: str


class MapState(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    rooms: list[MapRoom]
    exits: list[MapExit]


class ClientState(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    room_id: str
    room_name: str
    inventory: list[InventoryEntry]
    map: MapState
