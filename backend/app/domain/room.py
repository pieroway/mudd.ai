from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict
from app.domain.door import Door


@dataclass
class Room:
    id: str
    name: str
    description: str
    exits: Dict[str, str] = field(default_factory=dict)
    items: list[str] = field(default_factory=list)
    doors: dict[str, Door] = field(default_factory=dict)

    def look(self, items_in_room: list[str] | None = None) -> str:
        """Return a human-readable description for the room, including items."""
        if items_in_room is None:
            items_in_room = []

        exits_text = ", ".join(sorted(self.exits.keys())) if self.exits else "none"

        description = f"{self.name}\n{self.description}\nExits: {exits_text}"
        if self.doors:
            description += '\nDoors: ' + ', '.join(
                f"{direction}: {door.name} ({'open' if door.is_open else 'closed'})"
                for direction, door in sorted(self.doors.items()))

        if items_in_room:
            items_text = ", ".join(items_in_room)
            description += f"\n\nYou see: {items_text}"

        return description
