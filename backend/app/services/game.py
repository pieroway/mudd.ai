from __future__ import annotations

import asyncio
from secrets import choice
from typing import Any
from collections.abc import Awaitable, Callable

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.ai.models import InterpretCommandRequest, InterpretCommandResponse
from app.ai.provider import AIProvider, AIProviderError
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
        self,
        session_factory: async_sessionmaker[AsyncSession] | None = None,
        ai_provider: AIProvider | None = None,
        ai_command_timeout_seconds: float = 5.0,
    ) -> None:
        self.session_factory = session_factory or get_session_factory()
        self.ai_provider = ai_provider
        self.ai_command_timeout_seconds = ai_command_timeout_seconds
        self._session_players: dict[str, str] = {}
        self._session_usernames: dict[str, str] = {}
        self._active_usernames: set[str] = set()
        self._connection_lock = asyncio.Lock()
        self._command_lock = asyncio.Lock()

    async def connect_player(
        self, session_id: str, username: str, *, player_id: str | None = None
    ) -> Player:
        display_name, normalized_username = normalize_username(username)
        async with self._connection_lock:
            if normalized_username in self._active_usernames:
                raise UsernameInUseError("That username is already connected.")

            async with self.session_factory() as session:
                async with session.begin():
                    repository = GameRepository(session)
                    if player_id is None:
                        # Internal deterministic fixtures; network callers supply authenticated ID.
                        player_record = await repository.get_or_create_player(
                            display_name, normalized_username
                        )
                        player_id = player_record.id
                    player = await repository.load_player(player_id)

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

    async def execute(
        self,
        session_id: str,
        raw_command: str,
        *,
        authorization_check: Callable[[], Awaitable[bool]] | None = None,
    ) -> dict[str, Any]:
        player_id = self._session_players.get(session_id)
        if player_id is None:
            raise KeyError(f"No active player session: {session_id}")

        command = parse_command(raw_command)
        command_source = "classic"
        if command.get("action") == "unknown" and self.ai_provider is not None:
            command_source = "ai"
            try:
                proposed = await asyncio.wait_for(
                    self.ai_provider.interpret_command(
                        InterpretCommandRequest(raw_input=raw_command)
                    ),
                    timeout=self.ai_command_timeout_seconds,
                )
                validated = InterpretCommandResponse.model_validate(proposed)
            except (AIProviderError, TimeoutError, ValidationError):
                return {
                    "success": False,
                    "output": (
                        "I couldn't interpret that command. " "Try 'help' for available commands."
                    ),
                    "metadata": {"command_source": command_source},
                }
            command = validated.command.model_dump()
        async with self._command_lock:
            if authorization_check is not None and not await authorization_check():
                return {
                    "success": False,
                    "output": "Session expired. Please sign in again.",
                    "metadata": {"command_source": command_source},
                }
            result = await self._execute_locked(session_id, player_id, command)
        result["metadata"] = {"command_source": command_source}
        return result

    async def _execute_locked(
        self, session_id: str, player_id: str, command: dict[str, Any]
    ) -> dict[str, Any]:
        active_sessions = dict(self._session_players)
        active_player_ids = list(active_sessions.values())

        if command.get("action") in {"say", "tell"}:
            return await self._speech_result(
                session_id, player_id, command, active_sessions, active_player_ids
            )

        if command.get("action") == "who":
            return await self._who_result(command, active_player_ids)

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
                world, player = await repository.load_world(player_record, lock_items=lock_items)
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
                if command.get("action") in {"look", "move"} and result.get("success"):
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
                if result.get("success"):
                    activity_events = self._activity_events(
                        session_id,
                        command,
                        player,
                        active_players,
                        active_sessions,
                    )
                    if activity_events:
                        result.setdefault("events", []).extend(activity_events)
                await repository.persist_world(
                    world,
                    player,
                    player_record,
                    persist_items=lock_items,
                )
                return result

    async def _who_result(
        self, command: dict[str, Any], active_player_ids: list[str]
    ) -> dict[str, Any]:
        raw_page = command.get("page")
        try:
            page = int(raw_page) if raw_page is not None else 1
        except (TypeError, ValueError):
            return {"success": False, "output": "Usage: who [page]."}
        if page < 1:
            return {"success": False, "output": "Page number must be at least 1."}

        async with self.session_factory() as session:
            repository = GameRepository(session)
            records = await repository.load_players(active_player_ids)
            room_names = await repository.room_names({record.current_room_id for record in records})

        records.sort(key=lambda record: record.username.casefold())
        page_size = 25
        page_count = max(1, (len(records) + page_size - 1) // page_size)
        if page > page_count:
            return {
                "success": False,
                "output": f"There are only {page_count} pages of connected players.",
            }

        start = (page - 1) * page_size
        visible_records = records[start : start + page_size]
        heading = f"Players online ({len(records)})"
        if page_count > 1:
            heading += f" — page {page}/{page_count}"
        lines = [f"{heading}:"]
        lines.extend(
            f"- {record.username} — {room_names[record.current_room_id]}"
            for record in visible_records
        )
        return {"success": True, "output": "\n".join(lines)}

    @staticmethod
    def _activity_events(
        session_id: str,
        command: dict[str, Any],
        player: Player,
        active_players: list[Any],
        active_sessions: dict[str, str],
    ) -> list[dict[str, str]]:
        action_value = command.get("action")
        action = action_value if isinstance(action_value, str) else ""
        sender_before = next(record for record in active_players if record.id == player.id)
        sessions_by_player = {
            player_id: candidate_session for candidate_session, player_id in active_sessions.items()
        }
        events: list[dict[str, str]] = []

        if action == "move":
            direction_value = command.get("direction")
            direction = direction_value if isinstance(direction_value, str) else ""
            opposite = {
                "north": "south",
                "south": "north",
                "east": "west",
                "west": "east",
                "up": "below",
                "down": "above",
            }.get(direction, direction)
            for record in active_players:
                recipient_session = sessions_by_player.get(record.id)
                if recipient_session is None or recipient_session == session_id:
                    continue
                if record.current_room_id == sender_before.current_room_id:
                    events.append(
                        {
                            "session_id": recipient_session,
                            "text": f"{player.name} leaves to the {direction}.",
                        }
                    )
                elif record.current_room_id == player.current_room_id:
                    events.append(
                        {
                            "session_id": recipient_session,
                            "text": f"{player.name} arrives from the {opposite}.",
                        }
                    )
            return events

        target = command.get("target")
        activity = {
            "take": f"{player.name} picks up the {target}.",
            "drop": f"{player.name} drops the {target}.",
            "open": f"{player.name} opens the {target}.",
            "close": f"{player.name} closes the {target}.",
            "put": f"{player.name} puts the {target} into a container.",
            "take_from": f"{player.name} takes the {target} from a container.",
            "give": f"{player.name} gives the {target} to another player.",
        }.get(action)
        if activity is None:
            return events

        direct_recipient_name = (
            (command.get("target_player") or "").casefold() if action == "give" else None
        )
        for record in active_players:
            recipient_session = sessions_by_player.get(record.id)
            if (
                recipient_session is not None
                and recipient_session != session_id
                and record.username.casefold() != direct_recipient_name
                and record.current_room_id == player.current_room_id
            ):
                events.append({"session_id": recipient_session, "text": activity})
        return events

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
            usage = (
                "Usage: say to <player> <message>."
                if command.get("action") == "tell"
                else "Say what?"
            )
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
                return {
                    "success": False,
                    "output": f"{target_name or 'That player'} is not connected.",
                }
            recipient = players[active_sessions[recipient_session]]
            return {
                "success": True,
                "output": f'You tell {recipient.username}, "{message}"',
                "events": [
                    {
                        "session_id": recipient_session,
                        "text": f'{sender.username} tells you, "{message}"',
                    }
                ],
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
