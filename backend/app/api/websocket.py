"""WebSocket endpoints for the MUD game."""

import asyncio
import logging
from collections import defaultdict, deque
from time import monotonic
from typing import Set
from uuid import uuid4

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.ai.factory import create_ai_provider
from app.commands.parser import parse_command
from app.config import Settings
from app.services.game import GameService, InvalidUsernameError, UsernameInUseError
from app.services.auth import resolve_session
from app.api.auth import COOKIE_NAME

logger = logging.getLogger(__name__)

router = APIRouter()

active_connections: Set[WebSocket] = set()
connections_by_session: dict[str, WebSocket] = {}
authenticated_tokens: dict[WebSocket, str] = {}
settings = Settings()
game_service = GameService(
    ai_provider=create_ai_provider(settings),
    ai_command_timeout_seconds=settings.ai_command_timeout_seconds,
)
connection_attempts: dict[str, deque[float]] = defaultdict(deque)


def _within_rate_limit(timestamps: deque[float], limit: int, window: float) -> bool:
    now = monotonic()
    while timestamps and timestamps[0] <= now - window:
        timestamps.popleft()
    if len(timestamps) >= limit:
        return False
    timestamps.append(now)
    return True


def _connection_attempt_allowed(client_host: str) -> bool:
    timestamps = connection_attempts.get(client_host)
    if timestamps is None:
        if len(connection_attempts) >= settings.max_tracked_client_addresses:
            return False
        timestamps = deque()
        connection_attempts[client_host] = timestamps
    return _within_rate_limit(
        timestamps,
        settings.connection_attempt_limit,
        settings.connection_attempt_window_seconds,
    )


async def _send_json(websocket: WebSocket, message: dict) -> bool:
    """Bound writes so a slow client cannot hold a server task indefinitely."""
    try:
        token = authenticated_tokens.get(websocket)
        if (
            message.get("type") in {"game_output", "system"}
            and token
            and await resolve_session(token) is None
        ):
            await websocket.close(code=1008)
            return False
        await asyncio.wait_for(
            websocket.send_json(message),
            timeout=settings.outbound_send_timeout_seconds,
        )
        return True
    except (TimeoutError, WebSocketDisconnect):
        logger.warning("Dropped an outbound WebSocket message to a slow client")
        return False


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for persistent game sessions."""
    if not settings.allows_origin(websocket.headers.get("origin")):
        logger.warning("Rejected WebSocket connection from an untrusted origin")
        await websocket.close(code=1008)
        return

    client_host = websocket.client.host if websocket.client else "unknown"
    if not _connection_attempt_allowed(client_host):
        logger.warning("Rejected WebSocket connection after excessive attempts")
        await websocket.close(code=1013)
        return

    if len(active_connections) >= settings.max_websocket_connections:
        logger.warning("Rejected WebSocket connection because capacity was reached")
        await websocket.close(code=1013)
        return

    auth_token = websocket.cookies.get(COOKIE_NAME)
    identity = await resolve_session(auth_token)
    if identity is None or auth_token is None:
        await websocket.close(code=1008)
        return
    session_id = str(uuid4())
    username = identity.username
    connected = False
    command_timestamps: deque[float] = deque()

    await websocket.accept()
    active_connections.add(websocket)
    connections_by_session[session_id] = websocket
    authenticated_tokens[websocket] = auth_token

    async def still_authorized() -> bool:
        return await resolve_session(auth_token) == identity

    try:
        try:
            player = await game_service.connect_player(
                session_id, username, player_id=identity.player_id
            )
            connected = True
        except UsernameInUseError:
            await _send_json(
                websocket, {"type": "error", "text": "That username is already connected."}
            )
            await websocket.close(code=1008)
            return
        except InvalidUsernameError as error:
            await _send_json(websocket, {"type": "error", "text": str(error)})
            await websocket.close(code=1008)
            return

        room = await game_service.room_for_player(player.id)
        await _send_json(
            websocket,
            {
                "type": "system",
                "text": f"Welcome to the MUD! You stand in the {room.name}.",
                "room_name": room.name,
                "room_description": room.description,
            },
        )

        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30)
            except TimeoutError:
                data = None
            if await resolve_session(auth_token) != identity:
                await _send_json(
                    websocket, {"type": "error", "text": "Session expired. Please sign in again."}
                )
                await websocket.close(code=1008)
                return
            if data is None:
                continue
            command_bytes = len(data.encode("utf-8"))
            if command_bytes > settings.max_command_bytes:
                await _send_json(websocket, {"type": "error", "text": "Command is too large."})
                await websocket.close(code=1009)
                return
            if not _within_rate_limit(
                command_timestamps,
                settings.command_rate_limit,
                settings.command_rate_window_seconds,
            ):
                await _send_json(
                    websocket,
                    {"type": "error", "text": "Command rate limit exceeded."},
                )
                await websocket.close(code=1008)
                return
            action = str(parse_command(data).get("action", "unknown"))
            started_at = monotonic()
            logger.debug(
                "Command received session_id=%s action=%s bytes=%d",
                session_id,
                action,
                command_bytes,
            )

            try:
                result = await game_service.execute(
                    session_id, data, authorization_check=still_authorized
                )
                events = result.pop("events", [])
                logger.debug(
                    "Command completed session_id=%s action=%s success=%s elapsed_ms=%.1f",
                    session_id,
                    action,
                    bool(result.get("success", False)),
                    (monotonic() - started_at) * 1000,
                )
                await _send_json(
                    websocket,
                    {
                        "type": "game_output",
                        "success": result.get("success", False),
                        "text": result.get("output", ""),
                        "room_id": result.get("room_id"),
                        "metadata": result.get("metadata", {}),
                    },
                )
                for event in events:
                    recipient = connections_by_session.get(event["session_id"])
                    if recipient is not None:
                        await _send_json(
                            recipient,
                            {"type": "game_output", "success": True, "text": event["text"]},
                        )
            except Exception:
                logger.exception("Command execution error")
                await _send_json(
                    websocket, {"type": "error", "text": "An internal error occurred."}
                )
    except WebSocketDisconnect:
        logger.info("Client disconnected")
    except Exception:
        logger.exception("WebSocket error")
    finally:
        active_connections.discard(websocket)
        connections_by_session.pop(session_id, None)
        authenticated_tokens.pop(websocket, None)
        if connected:
            await game_service.disconnect_player(session_id)
