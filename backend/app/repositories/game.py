from __future__ import annotations

from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.item import Item
from app.domain.player import Player
from app.domain.room import Room
from app.models import ExitRecord, ItemRecord, PlayerRecord, RoomRecord


class GameRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

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

    async def load_world(
        self, player_record: PlayerRecord, *, lock_items: bool = False
    ) -> tuple[dict[str, object], Player]:
        room_records = (await self.session.scalars(select(RoomRecord))).all()
        exit_records = (await self.session.scalars(select(ExitRecord))).all()
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

        items = {
            record.id: Item(
                id=record.id,
                name=record.name,
                description=record.description,
                room_id=record.room_id,
                owned_by=record.owner_id,
            )
            for record in item_records
        }
        inventory = [record.id for record in item_records if record.owner_id == player_record.id]
        player = Player(
            id=player_record.id,
            name=player_record.username,
            current_room_id=player_record.current_room_id,
            inventory=inventory,
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
        if not persist_items:
            return

        domain_items: dict[str, Item] = world["items"]  # type: ignore[assignment]
        item_records = (await self.session.scalars(select(ItemRecord))).all()
        for record in item_records:
            domain_item = domain_items[record.id]
            record.room_id = domain_item.room_id
            record.owner_id = domain_item.owned_by

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
