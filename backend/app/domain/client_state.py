"""Explicit, player-visible data for optional client panels."""

from pydantic import BaseModel, ConfigDict


class InventoryEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    id: str
    name: str


class ClientState(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    room_id: str
    room_name: str
    inventory: list[InventoryEntry]
