from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Item:
    id: str
    name: str
    description: str
    room_id: str | None = None
    owned_by: str | None = None
    container_id: str | None = None
    can_open: bool = False
    is_open: bool = False
    can_use: bool = False
    use_message: str | None = None
    is_light_source: bool = False
    is_lit: bool = False
    fuel_remaining: int | None = None

    def is_in_room(self, room_id: str) -> bool:
        return self.room_id == room_id and self.owned_by is None

    def take_by(self, player_id: str) -> None:
        self.room_id = None
        self.container_id = None
        self.owned_by = player_id

    def drop_in(self, room_id: str) -> None:
        self.owned_by = None
        self.container_id = None
        self.room_id = room_id

    def put_in(self, container_id: str) -> None:
        self.room_id = None
        self.owned_by = None
        self.container_id = container_id
