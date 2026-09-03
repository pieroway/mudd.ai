from __future__ import annotations

import asyncio
from secrets import choice
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


SELF_TALK_RESPONSES = (
    "Stop talking to yourself. You are putting off crazy vibes.",
    "You whisper to yourself. Somehow, you still look surprised by the reply.",
    "Talking to yourself again? The room is beginning to worry.",
    "You address yourself with great importance. Nobody is impressed.",
    "Your private conversation with yourself remains extremely private.",
    "You tell yourself a secret you already knew. Remarkable work.",
)


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
        self._command_lock = asyncio.Lock()

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
        async with self._command_lock:
            return await self._execute_locked(session_id, player_id, command)

    async def _execute_locked(
        self, session_id: str, player_id: str, command: dict[str, Any]
    ) -> dict[str, Any]:
        active_sessions = dict(self._session_players)
        active_player_ids = list(active_sessions.values())

        if command.get("action") in {"say", "tell"}:
            return await self._speech_result(
                session_id, player_id, command, active_sessions, active_player_ids
            )

        lock_items = command.get("action") in {
            "take",
            "take_from",
            "put",
            "drop",
            "open",
            "close",
            "use",
            "extinguish",
            "move",
            "give",
        }
        async with self.session_factory() as session:
            async with session.begin():
                repository = GameRepository(session)
                player_record = await repository.load_player_for_update(player_id)
                world, player = await repository.load_world(
                    player_record, lock_items=lock_items
                )
                domain_players: dict[str, Player] = world["players"]  # type: ignore[assignment]
                active_players = await repository.load_players(active_player_ids)
                for record in active_players:
                    domain_players[record.id] = Player(
                        id=record.id,
                        name=record.username,
                        current_room_id=record.current_room_id,
                        inventory=[],
                    )
                result: dict[str, Any] = execute_command(command, player, world)
                if command.get("action") == "look":
                    others = sorted(
                        candidate.name
                        for candidate in domain_players.values()
                        if candidate.id != player.id
                        and candidate.current_room_id == player.current_room_id
                    )
                    if others:
                        result["output"] += f"\nAlso here: {', '.join(others)}."
                recipient_id = result.pop("recipient_id", None)
                recipient_output = result.pop("recipient_output", None)
                if recipient_id and recipient_output:
                    recipient_session = next(
                        (
                            candidate_session
                            for candidate_session, candidate_id in active_sessions.items()
                            if candidate_id == recipient_id
                        ),
                        None,
                    )
                    if recipient_session:
                        result["events"] = [
                            {"session_id": recipient_session, "text": recipient_output}
                        ]
                await repository.persist_world(
                    world,
                    player,
                    player_record,
                    persist_items=lock_items,
                )
                return result

    async def _speech_result(
        self,
        session_id: str,
        player_id: str,
        command: dict[str, Any],
        active_sessions: dict[str, str],
        active_player_ids: list[str],
    ) -> dict[str, Any]:
        message = command.get("message")
        if not message:
            usage = "Usage: say to <player> <message>." if command.get("action") == "tell" else "Say what?"
            return {"success": False, "output": usage}

        async with self.session_factory() as session:
            repository = GameRepository(session)
            records = await repository.load_players(active_player_ids)
        players = {record.id: record for record in records}
        sender = players[player_id]

        if command.get("action") == "tell":
            target_name = command.get("target_player")
            if (target_name or "").casefold() == self._session_usernames[session_id]:
                return {
                    "success": False,
                    "output": choice(SELF_TALK_RESPONSES),
                }
            recipient_session = next(
                (
                    candidate_session
                    for candidate_session, normalized in self._session_usernames.items()
                    if normalized == (target_name or "").casefold()
                ),
                None,
            )
            if recipient_session is None:
                return {"success": False, "output": f"{target_name or 'That player'} is not connected."}
            recipient = players[active_sessions[recipient_session]]
            return {
                "success": True,
                "output": f'You tell {recipient.username}, "{message}"',
                "events": [{"session_id": recipient_session, "text": f'{sender.username} tells you, "{message}"'}],
            }

        events = [
            {"session_id": candidate_session, "text": f'{sender.username} says, "{message}"'}
            for candidate_session, candidate_id in active_sessions.items()
            if candidate_session != session_id
            and players[candidate_id].current_room_id == sender.current_room_id
        ]
        return {
            "success": True,
            "output": f'You say, "{message}"',
            "events": events,
        }

    async def inventory_for_player(self, player_id: str) -> list[str]:
        async with self.session_factory() as session:
            return await GameRepository(session).inventory_for_player(player_id)

    async def room_for_player(self, player_id: str) -> Room:
        async with self.session_factory() as session:
            return await GameRepository(session).room_for_player(player_id)
