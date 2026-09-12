from dataclasses import dataclass


@dataclass
class Door:
    id: str
    name: str
    description: str
    room_id: str
    destination_room_id: str
    is_open: bool = False
