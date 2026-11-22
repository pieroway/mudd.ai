from dataclasses import dataclass


@dataclass
class Door:
    id: str
    name: str
    description: str
    room_id: str
    destination_room_id: str
    is_open: bool = False
    lock_id: str | None = None
    is_locked: bool = False
    is_hidden: bool = False
    is_jammed: bool = False

    def status(self) -> str:
        if self.is_jammed:
            return "jammed"
        if self.is_locked:
            return "locked"
        return "open" if self.is_open else "closed"
