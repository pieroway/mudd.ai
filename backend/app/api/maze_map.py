"""Administrator-only view of the maze around the signed-in character."""

from collections import Counter

from fastapi import APIRouter, HTTPException, Request, Response
from sqlalchemy import select

from app.api.auth import COOKIE_NAME
from app.db import get_session_factory
from app.engine.rail import CART
from app.models import AccountRecord, ExitRecord, ItemRecord, PlayerRecord, RoomRecord
from app.models.game import DoorRecord
from app.services.auth import resolve_session

router = APIRouter()


@router.get("/auth/maze-map")
async def maze_map(request: Request, response: Response):
    response.headers["Cache-Control"] = "no-store"
    identity = await resolve_session(request.cookies.get(COOKIE_NAME))
    if identity is None:
        raise HTTPException(401, "Please sign in.")
    async with get_session_factory()() as session:
        account = await session.get(AccountRecord, identity.account_id)
        if account is None or not account.is_admin:
            raise HTTPException(403, "The maze map requires admin access.")
        player = await session.get(PlayerRecord, account.player_id)
        current = await session.get(RoomRecord, player.current_room_id) if player else None
        region = current.conditions.get("maze", {}).get("region_id") if current else None
        if current is None or not region:
            raise HTTPException(404, "Enter a generated maze to open its admin map.")
        rooms = list(await session.scalars(select(RoomRecord).where(
            RoomRecord.conditions["maze"]["region_id"].astext == region
        ).order_by(RoomRecord.id)))
        by_id = {room.id: room for room in rooms}
        carts = Counter(await session.scalars(select(ItemRecord.room_id).where(
            ItemRecord.template_id == CART, ItemRecord.room_id.in_(by_id)
        )))
        exits = (await session.execute(
            select(ExitRecord, DoorRecord).outerjoin(DoorRecord, ExitRecord.door_id == DoorRecord.id)
            .where(ExitRecord.room_id.in_(by_id)).order_by(ExitRecord.room_id, ExitRecord.direction)
        )).all()
    return {
        "current_room_id": current.id,
        "rooms": [
            {"id": room.id, "name": room.name, "x": room.conditions["maze"]["x"],
             "y": room.conditions["maze"]["y"], "z": room.conditions["maze"]["z"],
             "carts": carts[room.id]}
            for room in rooms
        ],
        "exits": [
            {"room_id": edge.room_id, "destination_room_id": edge.destination_room_id,
             "direction": edge.direction,
             "rail": edge.direction in by_id[edge.room_id].conditions.get("rail", []),
             "door": door.name if door else None, "hidden": bool(door and door.is_hidden),
             "locked": bool(door and door.is_locked), "jammed": bool(door and door.is_jammed),
             "open": bool(door and door.is_open)}
            for edge, door in exits
        ],
    }
