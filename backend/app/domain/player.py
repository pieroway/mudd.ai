from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Player:
    id: str
    name: str
    current_room_id: str
    inventory: list[str] = field(default_factory=list)

    def move(self, room_id: str) -> None:
        self.current_room_id = room_id
