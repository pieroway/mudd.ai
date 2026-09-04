"""WebSocket endpoints for the MUD game."""

import logging
from typing import Set
from uuid import uuid4

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.config import Settings
from app.services.game import GameService, InvalidUsernameError, UsernameInUseError

logger = logging.getLogger(__name__)

router = APIRouter()

active_connections: Set[WebSocket] = set()
connections_by_session: dict[str, WebSocket] = {}
game_service = GameService()
settings = Settings()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for persistent game sessions."""
    if not settings.allows_origin(websocket.headers.get("origin")):
        logger.warning("Rejected WebSocket connection from an untrusted origin")
        await websocket.close(code=1008)
        return

    session_id = str(uuid4())
    username = websocket.query_params.get("username", "")
    connected = False

    await websocket.accept()
    active_connections.add(websocket)
    connections_by_session[session_id] = websocket

    try:
        try:
            player = await game_service.connect_player(session_id, username)
            connected = True
        except UsernameInUseError:
            await websocket.send_json(
                {"type": "error", "text": "That username is already connected."}
            )
            await websocket.close(code=1008)
            return
        except InvalidUsernameError as error:
            await websocket.send_json({"type": "error", "text": str(error)})
            await websocket.close(code=1008)
            return

        room = await game_service.room_for_player(player.id)
        await websocket.send_json(
            {
                "type": "system",
                "text": f"Welcome to the MUD! You stand in the {room.name}.",
                "room_name": room.name,
                "room_description": room.description,
            }
        )

        while True:
            data = await websocket.receive_text()
            logger.debug("Received command: %s", data)

            try:
                result = await game_service.execute(session_id, data)
                events = result.pop("events", [])
                await websocket.send_json(
                    {
                        "type": "game_output",
                        "success": result.get("success", False),
                        "text": result.get("output", ""),
                        "room_id": result.get("room_id"),
                    }
                )
                for event in events:
                    recipient = connections_by_session.get(event["session_id"])
                    if recipient is not None:
                        await recipient.send_json(
                            {"type": "game_output", "success": True, "text": event["text"]}
                        )
            except Exception:
                logger.exception("Command execution error")
                await websocket.send_json(
                    {"type": "error", "text": "An internal error occurred."}
                )
    except WebSocketDisconnect:
        logger.info("Client disconnected")
    except Exception:
        logger.exception("WebSocket error")
    finally:
        active_connections.discard(websocket)
        connections_by_session.pop(session_id, None)
        if connected:
            await game_service.disconnect_player(session_id)
