"""WebSocket endpoints for the MUD game."""

import logging
from uuid import uuid4

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Set

from app.services.game import GameService

logger = logging.getLogger(__name__)

router = APIRouter()

active_connections: Set[WebSocket] = set()
game_service = GameService()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for MUD game communication."""
    session_id = str(uuid4())
    username = websocket.query_params.get("username", "Guest")

    await websocket.accept()
    active_connections.add(websocket)
    game_service.connect_player(session_id, username)

    try:
        # Send welcome message
        welcome_msg = {
            "type": "system",
            "text": "Welcome to the MUD! You stand in the Town Square.",
            "room_name": "Town Square",
            "room_description": "A bustling marketplace at the heart of the town.",
        }
        await websocket.send_json(welcome_msg)

        # Listen for client messages
        while True:
            data = await websocket.receive_text()
            logger.debug(f"Received command: {data}")

            try:
                result = game_service.execute(session_id, data)

                # Send result to client
                response = {
                    "type": "game_output",
                    "success": result.get("success", False),
                    "text": result.get("output", ""),
                    "room_id": result.get("room_id"),
                }
                await websocket.send_json(response)

            except Exception as e:
                logger.error(f"Command execution error: {e}")
                error_response = {
                    "type": "error",
                    "text": f"An error occurred: {str(e)}",
                }
                await websocket.send_json(error_response)

    except WebSocketDisconnect:
        logger.info("Client disconnected")
    except Exception as e:
        logger.error("WebSocket error: %s", e)
    finally:
        active_connections.discard(websocket)
        game_service.disconnect_player(session_id)
