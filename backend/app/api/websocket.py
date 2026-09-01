"""WebSocket endpoints for the MUD game."""

import logging
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Set, Dict, Any

from app.commands.parser import parse_command
from app.engine.executor import execute_command
from tests.fixtures.world import seed_world

logger = logging.getLogger(__name__)

router = APIRouter()

# Active WebSocket connections (temporary, single-player for now)
active_connections: Set[WebSocket] = set()

# Game world state (shared across all connections for now)
# TODO: Make this per-player once we add auth and persistence
game_world: Dict[str, Any] = seed_world()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for MUD game communication."""
    await websocket.accept()
    active_connections.add(websocket)

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
                # Parse and execute command
                parsed = parse_command(data)
                result = execute_command(parsed, game_world["players"]["alan"], game_world)

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
        active_connections.discard(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        active_connections.discard(websocket)
