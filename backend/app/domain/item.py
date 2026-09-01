from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Item:
    id: str
    name: str
    description: str
    room_id: str | None = None
    owned_by: str | None = None

    def is_in_room(self, room_id: str) -> bool:
        return self.room_id == room_id and self.owned_by is None
