from __future__ import annotations

from copy import deepcopy
from uuid import uuid4

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.item import Item
from app.domain.item_template import ItemTemplate
from app.domain.item_context import visible, describe, suggested_actions, state_words
from app.domain.client_state import ClientState, InventoryEntry, MapState, MapRoom, MapExit
from app.models.game import PlayerDiscoveryRecord
from app.models.game import DoorRecord
from app.domain.door import Door
from app.domain.player import Player
from app.domain.room import Room
from app.models import ExitRecord, ItemRecord, ItemTemplateRecord, PlayerRecord, RoomRecord


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
        # Exit availability is visible locally; undiscovered destination data stays private.
        vertical = set((await self.session.execute(select(ExitRecord.room_id, ExitRecord.direction).where(
            ExitRecord.room_id.in_(known), ExitRecord.direction.in_(['up', 'down'])
        ))).all())
        return MapState(
            rooms=[MapRoom(id=room.id, name=room.name, building_id=room.building_id,
                           has_up=(room.id, 'up') in vertical, has_down=(room.id, 'down') in vertical)
                   for room in rooms],
            exits=[MapExit(room_id=edge.room_id, direction=edge.direction,
                           destination_room_id=edge.destination_room_id) for edge in exits],
        )

    async def client_state(self, player_id: str) -> ClientState:
        record = await self.session.get(PlayerRecord, player_id)
        if record is None:
            raise KeyError(f"Unknown player: {player_id}")
        world, player = await self.load_world(record)
        items: dict[str, Item] = world['items']  # type: ignore[assignment]

        def entry(item: Item, depth: int = 0) -> InventoryEntry:
            return InventoryEntry(id=item.id, name=item.name, description=describe(item, player, world, 'inventory'),
                quantity=item.quantity, location=item.relationships.get('slot') or item.relationships.get('placement') or
                ('inventory' if item.owned_by else 'room'), visible_state=state_words(item), actions=suggested_actions(item),
                contents=[entry(child, depth + 1) for child in sorted(items.values(), key=lambda obj: obj.id)
                          if depth < 8 and child.container_id == item.id and visible(child, player, world)])

        rooms: dict[str, Room] = world['rooms']  # type: ignore[assignment]
        return ClientState(
            room_id=player.current_room_id,
            room_name=rooms[player.current_room_id].name,
            inventory=[entry(item) for item in sorted(items.values(), key=lambda obj: obj.id)
                       if item.owned_by == player_id and visible(item, player, world)],
            visible_objects=[entry(item) for item in sorted(items.values(), key=lambda obj: obj.id)
                             if item.room_id == player.current_room_id and visible(item, player, world)],
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
        referenced_templates = {record.template_id for record in item_records if record.template_id}
        template_records = list((await self.session.scalars(select(ItemTemplateRecord).where(
            ItemTemplateRecord.id.in_(referenced_templates)))).all()) if referenced_templates else []
        templates = {
            template_record.id: ItemTemplate.model_validate(
                {
                    "template_id": template_record.id,
                    "name": template_record.name,
                    "aliases": template_record.aliases,
                    "categories": template_record.categories,
                    "description": {
                        "short": template_record.short_description,
                        "examine": template_record.examine_description,
                    },
                    "material": template_record.material,
                    "physical": template_record.physical,
                    "capabilities": template_record.capabilities,
                    "default_state": template_record.default_state,
                    "value": template_record.value,
                    "rarity": template_record.rarity,
                    "equipment_slots": template_record.equipment_slots,
                    "stackable": template_record.stackable,
                    "attributes": template_record.attributes,
                }
            )
            for template_record in template_records
        }

        rooms = {
            record.id: Room(
                id=record.id,
                name=record.name,
                description=record.description,
                conditions=deepcopy(record.conditions),
            )
            for record in room_records
        }
        for record in exit_records:
            rooms[record.room_id].exits[record.direction] = record.destination_room_id
            if record.door_id:
                rooms[record.room_id].doors[record.direction] = doors[record.door_id]

        items: dict[str, Item] = {}
        for item_record in item_records:
            template = templates.get(item_record.template_id) if item_record.template_id else None
            condition = deepcopy(item_record.condition)
            durability_value = condition.get("durability")
            maximum_durability_value = condition.get("maximum_durability")
            durability = (
                durability_value
                if isinstance(durability_value, int) and not isinstance(durability_value, bool)
                else None
            )
            maximum_durability = (
                maximum_durability_value
                if isinstance(maximum_durability_value, int)
                and not isinstance(maximum_durability_value, bool)
                else None
            )
            items[item_record.id] = Item(
                id=item_record.id,
                name=item_record.name,
                description=item_record.description,
                room_id=item_record.room_id,
                owned_by=item_record.owner_id,
                container_id=item_record.container_id,
                can_open=item_record.can_open,
                is_open=item_record.is_open,
                can_use=item_record.can_use,
                use_message=item_record.use_message,
                is_light_source=item_record.is_light_source,
                is_lit=item_record.is_lit,
                fuel_remaining=item_record.fuel_remaining,
                portable=item_record.portable,
                interaction_target_id=item_record.interaction_target_id,
                is_clean=item_record.is_clean,
                interaction_verb=item_record.interaction_verb,
                interaction_state=item_record.interaction_state,
                template_id=item_record.template_id,
                aliases=tuple(template.aliases) if template else (),
                categories=tuple(template.categories) if template else (),
                material=template.material if template else None,
                weight_kg=template.physical.weight_kg if template else None,
                size=template.physical.size if template else None,
                dimensions_cm=(
                    template.physical.dimensions_cm.model_dump() if template else {}
                ),
                capabilities=deepcopy(template.capabilities) if template else {},
                state=deepcopy(item_record.state_data),
                quantity=item_record.quantity,
                durability=durability,
                maximum_durability=maximum_durability,
                condition=condition,
                relationships=deepcopy(item_record.relationships),
                discovery=deepcopy(item_record.discovery),
                provenance=deepcopy(item_record.provenance),
                created_at=item_record.created_at,
                updated_at=item_record.updated_at,
            )
        inventory = [record.id for record in item_records if record.owner_id == player_record.id]
        player = Player(
            id=player_record.id,
            name=player_record.username,
            current_room_id=player_record.current_room_id,
            inventory=inventory,
            facing_direction=player_record.facing_direction,
            state=deepcopy(player_record.state_data),
        )
        world: dict[str, object] = {"rooms": rooms, "items": items, "players": {player.id: player}}
        world['_player_rooms'] = {pid: location for pid, location in (await self.session.execute(
            select(PlayerRecord.id, PlayerRecord.current_room_id))).all()}
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
        player_record.state_data = deepcopy(player.state)
        await self.discover_room(player.id, player.current_room_id)
        if not persist_items:
            return

        rooms: dict[str, Room] = world['rooms']  # type: ignore[assignment]
        domain_doors = {door.id: door for room in rooms.values() for door in room.doors.values()}
        door_records = (await self.session.scalars(select(DoorRecord).where(DoorRecord.id.in_(domain_doors)))).all()
        for door_record in door_records:
            door_record.is_open = domain_doors[door_record.id].is_open

        domain_items: dict[str, Item] = world["items"]  # type: ignore[assignment]
        item_records = list((await self.session.scalars(select(ItemRecord))).all())
        existing = {record.id for record in item_records}
        # Flush removals before new instances; only rules under the item lock mutate this set.
        for record in item_records:
            if record.id not in domain_items:
                await self.session.delete(record)
        for key, item in domain_items.items():
            if key not in existing:
                record = ItemRecord(id=item.id, name=item.name, description=item.description,
                    room_id=item.room_id, owner_id=item.owned_by, container_id=item.container_id,
                    template_id=item.template_id, can_open=item.can_open, can_use=item.can_use,
                    is_light_source=item.is_light_source, portable=item.portable)
                self.session.add(record)
                item_records.append(record)
        for record in item_records:
            if record.id not in domain_items:
                continue
            domain_item = domain_items[record.id]
            record.room_id = domain_item.room_id
            record.owner_id = domain_item.owned_by
            record.container_id = domain_item.container_id
            record.is_open = domain_item.is_open
            record.is_lit = domain_item.is_lit
            record.fuel_remaining = domain_item.fuel_remaining
            record.is_clean = domain_item.is_clean
            record.interaction_state = domain_item.interaction_state
            if domain_item.template_id:
                if domain_item.can_open:
                    domain_item.state['open'] = domain_item.is_open
                if domain_item.is_light_source:
                    domain_item.state['lit'] = domain_item.is_lit
                    domain_item.state['fuel_remaining'] = domain_item.fuel_remaining
                if domain_item.durability is not None:
                    domain_item.state['durability'] = domain_item.durability
            record.state_data = deepcopy(domain_item.state)
            condition = deepcopy(domain_item.condition)
            if domain_item.durability is not None:
                condition["durability"] = domain_item.durability
            if domain_item.maximum_durability is not None:
                condition["maximum_durability"] = domain_item.maximum_durability
            record.condition = condition
            record.quantity = domain_item.quantity
            record.relationships = deepcopy(domain_item.relationships)
            record.discovery = deepcopy(domain_item.discovery)
            record.provenance = deepcopy(domain_item.provenance)

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
