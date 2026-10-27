"""Private admin authoring and diagnostics for deterministic item instances."""

import json
from dataclasses import asdict
from uuid import uuid4
from typing import Any

from app.domain.catalogue import CATALOGUE
from app.domain.item import Item
from app.domain.room import Room
from app.domain.item_context import root
from app.domain.item_dependencies import provision_lock, validate_world_dependencies
from app.engine.item_rules import placement_error
from app.repositories.game import GameRepository
from app.repositories.world_proposals import WorldProposalRepository
from app.models import RoomRecord

ITEM_HELP = (
    "/item environment <json> | "
    '/item catalogue | /item spawn <template-id> [quantity] ["name"] | /item inspect <id> | '
    "/item lock <id> [key-room-id] [hiding-place-id] | /item place <id> <relationship> <target-id> | "
    '/item configure <id> \'{"readable":{"text":"..."}}\''
)


async def execute(factory, player_id, account_id, arguments, authorized) -> dict[str, Any]:
    if not account_id or not await authorized():
        return {
            "success": False,
            "output": "Item diagnostics and authoring require an active admin session.",
        }
    try:
        async with factory() as session, session.begin():
            record = await WorldProposalRepository(session).admin_player(account_id, player_id)
            if record is None or not await authorized():
                return {
                    "success": False,
                    "output": "Item diagnostics and authoring are available to admin users only.",
                }
            if not arguments:
                return {"success": False, "output": ITEM_HELP}
            operation = arguments[0].casefold()
            if operation == "environment" and len(arguments) == 2:
                data = json.loads(arguments[1])
                if not isinstance(data, dict) or set(data) - {"dark", "terrain", "shore"}:
                    raise ValueError("Room conditions support dark, terrain, and shore only.")
                if any(
                    key in data and not isinstance(data[key], bool) for key in ("dark", "shore")
                ):
                    raise ValueError("Dark and shore conditions must be booleans.")
                if "terrain" in data and data["terrain"] not in {
                    "land",
                    "river",
                    "lake",
                    "sheltered_water",
                }:
                    raise ValueError("Unsupported room terrain.")
                room = await session.get(RoomRecord, record.current_room_id, with_for_update=True)
                if room is None or not await authorized():
                    raise ValueError("The room or admin session is no longer available.")
                room.conditions = {**room.conditions, **data}
                return {"success": True, "output": "Updated the current room conditions."}
            if operation == "catalogue":
                return {
                    "success": True,
                    "output": "\n".join(f"{key}: {value.name}" for key, value in CATALOGUE.items()),
                }
            repo = GameRepository(session)
            record = await repo.load_player_for_update(player_id)
            world, player = await repo.load_world(record, lock_items=True)
            items: dict[str, Item] = world["items"]  # type: ignore[assignment]
            rooms: dict[str, Room] = world["rooms"]  # type: ignore[assignment]
            if operation == "spawn" and 2 <= len(arguments) <= 4:
                template = CATALOGUE[arguments[1]]
                quantity = int(arguments[2]) if len(arguments) >= 3 else 1
                if quantity > 1000000 or quantity > 1 and not template.stackable:
                    raise ValueError("This template cannot have that quantity.")
                item = Item.from_template(
                    str(uuid4()), template, room_id=player.current_room_id, quantity=quantity
                )
                if len(arguments) == 4:
                    if not 1 <= len(arguments[3]) <= 100:
                        raise ValueError("Use a name between 1 and 100 characters.")
                    item.name = arguments[3]
                items[item.id] = item
                text = f"Created {item.name}: {item.id} (template {template.template_id})."
            elif len(arguments) >= 2 and arguments[1] in items:
                item = items[arguments[1]]
                if operation == "inspect" and len(arguments) == 2:
                    try:
                        dependencies = validate_world_dependencies(items, rooms, world.get('_player_rooms'))
                    except ValueError as dependency_error:
                        dependencies = {"solvable": False, "reason": str(dependency_error)}
                    links = [
                        {
                            "object_id": obj.id,
                            "lock_id": obj.relationships.get("lock_id"),
                            "keys": [
                                {
                                    "id": key.id,
                                    "container_id": key.container_id,
                                    "room_id": key.room_id,
                                    "holder": key.owned_by,
                                }
                                for key in items.values()
                                if obj.relationships.get("lock_id")
                                in key.relationships.get("opens", [])
                            ],
                        }
                        for obj in items.values()
                        if obj.relationships.get("lock_id")
                    ]
                    return {
                        "success": True,
                        "output": json.dumps(
                            {
                                "item": asdict(item),
                                "dependencies": dependencies,
                                "key_dependency_graph": links,
                                "recent_actions": player.state.get("item_action_history", []),
                            },
                            default=str,
                            indent=2,
                        ),
                    }
                origin = root(item, items)
                if origin is None or not (
                    origin.room_id == player.current_room_id or origin.owned_by == player.id
                ):
                    raise ValueError("Move to the object before editing it.")
                if operation == "lock" and 2 <= len(arguments) <= 4:
                    key = provision_lock(
                        item,
                        items,
                        world["rooms"],
                        player.current_room_id,
                        key_room=arguments[2] if len(arguments) >= 3 else None,
                        hiding_place=arguments[3] if len(arguments) == 4 else None,
                        holder_rooms=world.get('_player_rooms'),
                    )
                    text = f"Locked {item.name}. Matching key: {key.name} ({key.id})."
                elif operation == "place" and len(arguments) == 4:
                    placement, target = arguments[2], items[arguments[3]]
                    if (
                        root(target, items).room_id != player.current_room_id
                        and root(target, items).owned_by != player.id
                    ):
                        raise ValueError("The destination must be in your room or inventory.")
                    if placement in {"resting_on", "contained_in"}:
                        error = placement_error(item, target, player, world, placement)
                        if error:
                            raise ValueError(error)
                    elif placement == "hidden_under":
                        if not (
                            target.has_capability("searchable") or target.has_capability("movable")
                        ):
                            raise ValueError("The hiding place must support discovery.")
                        if item.id == target.id or root(target, items).id == item.id:
                            raise ValueError("A hiding place cannot create a cycle.")
                        item.discovery = {"hidden": True, "discovered_by": []}
                        target.discovery["clue"] = "Something has disturbed the dust around it."
                    else:
                        raise ValueError("Use contained_in, resting_on, or hidden_under.")
                    if item.id in player.inventory:
                        player.inventory.remove(item.id)
                    item.put_in(target.id)
                    item.relationships["placement"] = placement
                    text = f"Placed {item.name}: {placement} {target.name}."
                elif operation == "configure" and len(arguments) == 3:
                    data = json.loads(arguments[2])
                    if (
                        not isinstance(data, dict)
                        or not data
                        or set(data)
                        - {
                            "readable",
                            "wet",
                            "fuel_remaining",
                            "clue",
                            "climb_destination",
                            "liquid",
                            "liquid_litres",
                            "alternative_access",
                        }
                    ):
                        raise ValueError("Unsupported item configuration.")
                    for name, value in data.items():
                        if name == "readable":
                            if (
                                not item.has_capability("readable")
                                or not isinstance(value, dict)
                                or set(value)
                                - {
                                    "text",
                                    "front",
                                    "back",
                                    "folds",
                                    "seal",
                                    "cover",
                                    "pages",
                                    "margins",
                                }
                                or any(
                                    not isinstance(part, str) or len(part) > 2000
                                    for part in value.values()
                                )
                            ):
                                raise ValueError("Readable parts must contain bounded plain text.")
                            item.state[name] = value
                        elif name == "wet":
                            if not isinstance(value, bool):
                                raise ValueError("Wet state must be a boolean.")
                            item.state[name] = value
                        elif name in {"fuel_remaining", "liquid_litres"}:
                            if (
                                not isinstance(value, (int, float))
                                or isinstance(value, bool)
                                or not 0 <= value <= 10000
                            ):
                                raise ValueError("Use a bounded nonnegative amount.")
                            if name == "fuel_remaining":
                                if not item.is_light_source or not isinstance(value, int):
                                    raise ValueError(
                                        "Fuel requires a light source and whole turns."
                                    )
                                item.fuel_remaining = value
                            else:
                                if not item.has_capability("fillable") or value > item.capabilities[
                                    "fillable"
                                ].get("capacity_litres", 0):
                                    raise ValueError("Liquid exceeds the vessel capacity.")
                                item.state[name] = value
                        elif name == "clue":
                            if not isinstance(value, str) or len(value) > 240:
                                raise ValueError("Clues are limited to 240 characters.")
                            item.discovery[name] = value
                        elif name == "alternative_access":
                            if not isinstance(value, list) or set(value) - {"pick_lock", "break"}:
                                raise ValueError(
                                    "Only explicit lock-picking or breaking alternatives are supported."
                                )
                            item.relationships[name] = value
                        elif name == "climb_destination":
                            if (
                                not item.has_capability("climbable")
                                or value not in rooms[player.current_room_id].exits.values()
                            ):
                                raise ValueError("Climbing must lead to an existing adjacent room.")
                            item.relationships[name] = value
                        elif name == "liquid":
                            if value not in {"water", "ale"} or not item.has_capability("fillable"):
                                raise ValueError("Use water or ale in a fillable vessel.")
                            item.state[name] = value
                    text = f"Configured {item.name}."
                else:
                    raise ValueError(ITEM_HELP)
            else:
                raise ValueError(ITEM_HELP)
            validate_world_dependencies(items, rooms, world.get('_player_rooms'))
            if (
                not await authorized()
                or await WorldProposalRepository(session).admin_player(account_id, player_id)
                is None
            ):
                raise ValueError("Admin session expired; no changes were saved.")
            await repo.persist_world(world, player, record, persist_items=True)
            return {"success": True, "output": text}
    except (ValueError, KeyError, TypeError) as error:
        return {
            "success": False,
            "output": str(error) if isinstance(error, ValueError) else ITEM_HELP,
        }
