from __future__ import annotations

from typing import Any

from app.commands.parser import parse_command
from app.domain.player import Player
from app.engine.executor import execute_command
from app.world import create_world


class GameService:
    """Coordinate player sessions with the authoritative game engine."""

    def __init__(self) -> None:
        self.world = create_world()

    def connect_player(self, session_id: str, name: str) -> Player:
        player = Player(
            id=session_id,
            name=name.strip() or "Guest",
            current_room_id="town_square",
        )
        self.world["players"][session_id] = player
        return player

    def disconnect_player(self, session_id: str) -> None:
        self.world["players"].pop(session_id, None)

    def execute(self, session_id: str, raw_command: str) -> dict[str, Any]:
        player = self.world["players"].get(session_id)
        if player is None:
            raise KeyError(f"No active player session: {session_id}")

        result: dict[str, Any] = execute_command(parse_command(raw_command), player, self.world)
        return result
