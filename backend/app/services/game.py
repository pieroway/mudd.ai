from __future__ import annotations

import asyncio
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.commands.parser import parse_command
from app.db import get_session_factory
from app.domain.player import Player
from app.domain.room import Room
from app.engine.executor import execute_command
from app.repositories.game import GameRepository


class UsernameInUseError(ValueError):
    pass


class InvalidUsernameError(ValueError):
    pass


def normalize_username(username: str) -> tuple[str, str]:
    display_name = username.strip()
    if not display_name:
        raise InvalidUsernameError("Username is required.")
    if len(display_name) > 50:
        raise InvalidUsernameError("Username must be 50 characters or fewer.")
    return display_name, display_name.casefold()


class GameService:
    """Coordinate persistent players with transactional game commands."""

    def __init__(
        self, session_factory: async_sessionmaker[AsyncSession] | None = None
    ) -> None:
        self.session_factory = session_factory or get_session_factory()
        self._session_players: dict[str, str] = {}
        self._session_usernames: dict[str, str] = {}
        self._active_usernames: set[str] = set()
        self._connection_lock = asyncio.Lock()

    async def connect_player(self, session_id: str, username: str) -> Player:
        display_name, normalized_username = normalize_username(username)
        async with self._connection_lock:
            if normalized_username in self._active_usernames:
                raise UsernameInUseError("That username is already connected.")

            async with self.session_factory() as session:
                async with session.begin():
                    repository = GameRepository(session)
                    player_record = await repository.get_or_create_player(
                        display_name, normalized_username
                    )
                    player = await repository.load_player(player_record.id)

            self._session_players[session_id] = player.id
            self._session_usernames[session_id] = normalized_username
            self._active_usernames.add(normalized_username)
            return player

    async def disconnect_player(self, session_id: str) -> None:
        async with self._connection_lock:
            self._session_players.pop(session_id, None)
            normalized_username = self._session_usernames.pop(session_id, None)
            if normalized_username is not None:
                self._active_usernames.discard(normalized_username)

    async def execute(self, session_id: str, raw_command: str) -> dict[str, Any]:
        player_id = self._session_players.get(session_id)
        if player_id is None:
            raise KeyError(f"No active player session: {session_id}")

        command = parse_command(raw_command)
        lock_items = command.get("action") in {
            "take",
            "take_from",
            "put",
            "drop",
            "open",
            "close",
        }
        async with self.session_factory() as session:
            async with session.begin():
                repository = GameRepository(session)
                player_record = await repository.load_player_for_update(player_id)
                world, player = await repository.load_world(
                    player_record, lock_items=lock_items
                )
                result: dict[str, Any] = execute_command(command, player, world)
                await repository.persist_world(
                    world,
                    player,
                    player_record,
                    persist_items=lock_items,
                )
                return result

    async def inventory_for_player(self, player_id: str) -> list[str]:
        async with self.session_factory() as session:
            return await GameRepository(session).inventory_for_player(player_id)

    async def room_for_player(self, player_id: str) -> Room:
        async with self.session_factory() as session:
            return await GameRepository(session).room_for_player(player_id)
