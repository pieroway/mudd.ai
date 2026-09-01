"""WebSocket endpoints for the MUD game."""

import logging
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Set

logger = logging.getLogger(__name__)

router = APIRouter()

# Active WebSocket connections (temporary, single-player for now)
active_connections: Set[WebSocket] = set()


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
            logger.debug(f"Received: {data}")

            # Echo for now (placeholder)
            response = {
                "type": "game_output",
                "text": f"You entered: {data}",
            }
            await websocket.send_json(response)

    except WebSocketDisconnect:
        logger.info("Client disconnected")
        active_connections.discard(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        active_connections.discard(websocket)
