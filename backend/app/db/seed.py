from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ExitRecord, ItemRecord, RoomRecord
from app.world import create_world


async def seed_world(session: AsyncSession) -> None:
    """Insert the deterministic world without resetting persistent state."""
    world = create_world()

    for room in world["rooms"].values():
        if await session.get(RoomRecord, room.id) is None:
            session.add(RoomRecord(id=room.id, name=room.name, description=room.description))
    await session.flush()

    for room in world["rooms"].values():
        for direction, destination_room_id in room.exits.items():
            key = {"room_id": room.id, "direction": direction}
            if await session.get(ExitRecord, key) is None:
                session.add(
                    ExitRecord(
                        room_id=room.id,
                        direction=direction,
                        destination_room_id=destination_room_id,
                    )
                )

    for item in world["items"].values():
        record = await session.get(ItemRecord, item.id)
        if record is None:
            session.add(
                ItemRecord(
                    id=item.id,
                    name=item.name,
                    description=item.description,
                    room_id=item.room_id,
                    owner_id=None,
                    container_id=None,
                    can_open=item.can_open,
                    is_open=item.is_open,
                    can_use=item.can_use,
                    use_message=item.use_message,
                    is_light_source=item.is_light_source,
                    is_lit=item.is_lit,
                )
            )
        else:
            record.can_open = item.can_open
            record.can_use = item.can_use
            record.use_message = item.use_message
            record.is_light_source = item.is_light_source
