from __future__ import annotations

from uuid import uuid4

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.item import Item
from app.domain.client_state import ClientState, InventoryEntry, MapState, MapRoom, MapExit
from app.models.game import PlayerDiscoveryRecord
from app.models.game import DoorRecord
from app.domain.door import Door
from app.domain.player import Player
from app.domain.room import Room
from app.models import ExitRecord, ItemRecord, PlayerRecord, RoomRecord


class GameRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def discover_room(self, player_id: str, room_id: str) -> None:
        await self.session.execute(insert(PlayerDiscoveryRecord).values(
            player_id=player_id, room_id=room_id,
        ).on_conflict_do_nothing())

    async def map_state(self, player_id: str) -> MapState:
        known = select(PlayerDiscoveryRecord.room_id).where(
            PlayerDiscoveryRecord.player_id == player_id
        )
        rooms = (await self.session.scalars(select(RoomRecord).where(
            RoomRecord.id.in_(known)).order_by(RoomRecord.id))).all()
        exits = (await self.session.scalars(select(ExitRecord).where(
            ExitRecord.room_id.in_(known), ExitRecord.destination_room_id.in_(known)
        ).order_by(ExitRecord.room_id, ExitRecord.direction))).all()
        return MapState(
            rooms=[MapRoom(id=room.id, name=room.name) for room in rooms],
            exits=[MapExit(room_id=edge.room_id, direction=edge.direction,
                           destination_room_id=edge.destination_room_id) for edge in exits],
        )

    async def client_state(self, player_id: str) -> ClientState:
        # One query gives a consistent snapshot without loading hidden world data.
        statement = (
            select(RoomRecord.id, RoomRecord.name, ItemRecord.id, ItemRecord.name)
            .select_from(PlayerRecord)
            .join(RoomRecord, RoomRecord.id == PlayerRecord.current_room_id)
            .outerjoin(ItemRecord, ItemRecord.owner_id == PlayerRecord.id)
            .where(PlayerRecord.id == player_id)
            .order_by(ItemRecord.id)
        )
        rows = (await self.session.execute(statement)).all()
        if not rows:
            raise KeyError(f"Unknown player: {player_id}")
        return ClientState(
            room_id=rows[0][0],
            room_name=rows[0][1],
            inventory=[InventoryEntry(id=row[2], name=row[3]) for row in rows if row[2]],
            map=await self.map_state(player_id),
        )

    async def get_or_create_player(self, username: str, normalized_username: str) -> PlayerRecord:
        player_id = str(uuid4())
        insert_statement = (
            insert(PlayerRecord)
            .values(
                id=player_id,
                username=username,
                normalized_username=normalized_username,
                current_room_id="town_square",
            )
            .on_conflict_do_nothing(index_elements=[PlayerRecord.normalized_username])
            .returning(PlayerRecord.id)
        )
        inserted_id = (await self.session.execute(insert_statement)).scalar_one_or_none()
        lookup_statement = select(PlayerRecord).where(
            PlayerRecord.normalized_username == normalized_username
        )
        if inserted_id is not None:
            lookup_statement = select(PlayerRecord).where(PlayerRecord.id == inserted_id)
        return (await self.session.scalars(lookup_statement)).one()

    async def load_player_for_update(self, player_id: str) -> PlayerRecord:
        statement = select(PlayerRecord).where(PlayerRecord.id == player_id).with_for_update()
        return (await self.session.scalars(statement)).one()

    async def load_players(self, player_ids: list[str]) -> list[PlayerRecord]:
        if not player_ids:
            return []
        statement = select(PlayerRecord).where(PlayerRecord.id.in_(player_ids))
        return list((await self.session.scalars(statement)).all())

    async def room_names(self, room_ids: set[str]) -> dict[str, str]:
        if not room_ids:
            return {}
        statement = select(RoomRecord).where(RoomRecord.id.in_(room_ids))
        records = (await self.session.scalars(statement)).all()
        return {record.id: record.name for record in records}

    async def load_world(
        self, player_record: PlayerRecord, *, lock_items: bool = False
    ) -> tuple[dict[str, object], Player]:
        # Keep rooms, exits, doors and items consistent while a builder publishes.
        # Shared locks allow concurrent gameplay; publication takes the exclusive lock.
        await self.session.execute(text("SELECT pg_advisory_xact_lock_shared(50615001)"))
        room_records = (await self.session.scalars(select(RoomRecord))).all()
        exit_records = (await self.session.scalars(select(ExitRecord))).all()
        door_statement = select(DoorRecord).order_by(DoorRecord.id)
        if lock_items:
            door_statement = door_statement.with_for_update()
        door_records = (await self.session.scalars(door_statement)).all()
        doors = {record.id: Door(record.id, record.name, record.description, record.room_id,
                                record.destination_room_id, record.is_open) for record in door_records}
        item_statement = select(ItemRecord).order_by(ItemRecord.id)
        if lock_items:
            item_statement = item_statement.with_for_update()
        item_records = (await self.session.scalars(item_statement)).all()

        rooms = {
            record.id: Room(
                id=record.id,
                name=record.name,
                description=record.description,
            )
            for record in room_records
        }
        for record in exit_records:
            rooms[record.room_id].exits[record.direction] = record.destination_room_id
            if record.door_id:
                rooms[record.room_id].doors[record.direction] = doors[record.door_id]

        items = {
            record.id: Item(
                id=record.id,
                name=record.name,
                description=record.description,
                room_id=record.room_id,
                owned_by=record.owner_id,
                container_id=record.container_id,
                can_open=record.can_open,
                is_open=record.is_open,
                can_use=record.can_use,
                use_message=record.use_message,
                is_light_source=record.is_light_source,
                is_lit=record.is_lit,
                fuel_remaining=record.fuel_remaining,
                portable=record.portable,
            )
            for record in item_records
        }
        inventory = [record.id for record in item_records if record.owner_id == player_record.id]
        player = Player(
            id=player_record.id,
            name=player_record.username,
            current_room_id=player_record.current_room_id,
            inventory=inventory,
            facing_direction=player_record.facing_direction,
        )
        world: dict[str, object] = {"rooms": rooms, "items": items, "players": {player.id: player}}
        return world, player

    async def persist_world(
        self,
        world: dict[str, object],
        player: Player,
        player_record: PlayerRecord,
        *,
        persist_items: bool,
    ) -> None:
        player_record.current_room_id = player.current_room_id
        player_record.facing_direction = player.facing_direction
        await self.discover_room(player.id, player.current_room_id)
        if not persist_items:
            return

        rooms: dict[str, Room] = world['rooms']  # type: ignore[assignment]
        domain_doors = {door.id: door for room in rooms.values() for door in room.doors.values()}
        door_records = (await self.session.scalars(select(DoorRecord).where(DoorRecord.id.in_(domain_doors)))).all()
        for door_record in door_records:
            door_record.is_open = domain_doors[door_record.id].is_open

        domain_items: dict[str, Item] = world["items"]  # type: ignore[assignment]
        item_records = (await self.session.scalars(select(ItemRecord).where(ItemRecord.id.in_(domain_items)))).all()
        for record in item_records:
            domain_item = domain_items[record.id]
            record.room_id = domain_item.room_id
            record.owner_id = domain_item.owned_by
            record.container_id = domain_item.container_id
            record.is_open = domain_item.is_open
            record.is_lit = domain_item.is_lit
            record.fuel_remaining = domain_item.fuel_remaining

    async def load_player(self, player_id: str) -> Player:
        player_record = await self.session.get(PlayerRecord, player_id)
        if player_record is None:
            raise KeyError(f"Unknown player: {player_id}")
        _, player = await self.load_world(player_record)
        return player

    async def inventory_for_player(self, player_id: str) -> list[str]:
        statement = (
            select(ItemRecord.id).where(ItemRecord.owner_id == player_id).order_by(ItemRecord.id)
        )
        return list((await self.session.scalars(statement)).all())

    async def room_for_player(self, player_id: str) -> Room:
        player = await self.load_player(player_id)
        room_record = await self.session.get(RoomRecord, player.current_room_id)
        if room_record is None:
            raise KeyError(f"Unknown room: {player.current_room_id}")
        return Room(
            id=room_record.id,
            name=room_record.name,
            description=room_record.description,
        )
