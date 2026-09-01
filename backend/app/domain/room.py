from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class Room:
    id: str
    name: str
    description: str
    exits: Dict[str, str] = field(default_factory=dict)
    items: list[str] = field(default_factory=list)

    def look(self) -> str:
        """Return a human-readable description for the room."""
        exits_text = ", ".join(sorted(self.exits.keys())) if self.exits else "none"
        return f"{self.name}\n{self.description}\nExits: {exits_text}"
