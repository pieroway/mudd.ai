from __future__ import annotations


def _find_item(items, target):
    if not target:
        return None

    normalized_target = target.casefold()
    return next(
        (
            item
            for item in items.values()
            if item.id.casefold() == normalized_target or item.name.casefold() == normalized_target
        ),
        None,
    )


def _is_accessible(item, player):
    return item is not None and (
        item.is_in_room(player.current_room_id)
        or (item.id in player.inventory and item.owned_by == player.id)
    )


def execute_command(command, player, world):
    """Execute a parsed command against a deterministic test world."""
    action = command.get("action")

    if action == "look":
        room = world["rooms"][player.current_room_id]
        # Find items in this room
        items_here = [
            item.name for item in world["items"].values()
            if item.is_in_room(player.current_room_id)
        ]
        output = room.look(items_here)
        has_lit_light = any(
            item.owned_by == player.id and item.is_light_source and item.is_lit
            for item in world["items"].values()
        )
        if has_lit_light and room.exits:
            distant_rooms = ", ".join(
                f"{direction}: {world['rooms'][destination_id].name}"
                for direction, destination_id in sorted(room.exits.items())
            )
            output += f"\nTorchlight reaches farther. Beyond the exits: {distant_rooms}."
        return {"success": True, "output": output, "room_id": room.id}

    if action == "look_in":
        container_target = command.get("container")
        if not container_target:
            return {"success": False, "output": "Usage: look in <container>."}

        container = _find_item(world["items"], container_target)
        if not _is_accessible(container, player):
            return {
                "success": False,
                "output": f"You do not see a {container_target} here.",
            }
        if not container.can_open:
            return {"success": False, "output": f"The {container.name} is not a container."}
        if not container.is_open:
            return {"success": False, "output": f"The {container.name} is closed."}

        contents = sorted(
            item.name for item in world["items"].values() if item.container_id == container.id
        )
        if not contents:
            return {"success": True, "output": f"The {container.name} is empty."}
        return {
            "success": True,
            "output": f"The {container.name} contains: {', '.join(contents)}.",
        }

    if action == "move":
        direction = command.get("direction")
        room = world["rooms"][player.current_room_id]
        next_room_id = room.exits.get(direction)
        if not next_room_id:
            return {"success": False, "output": f"You cannot go {direction} from here.", "room_id": room.id}

        player.move(next_room_id)
        destination = world["rooms"][next_room_id]
        # Find items in destination room
        items_here = [
            item.name for item in world["items"].values()
            if item.is_in_room(next_room_id)
        ]
        extinguished = []
        for item in world["items"].values():
            if (
                item.owned_by == player.id
                and item.is_light_source
                and item.is_lit
                and item.fuel_remaining is not None
            ):
                item.fuel_remaining -= 1
                if item.fuel_remaining == 0:
                    item.is_lit = False
                    extinguished.append(item.name)

        output = f"You move {direction}.\n{destination.look(items_here)}"
        for item_name in sorted(extinguished):
            output += f"\nThe {item_name} sputters out."

        return {
            "success": True,
            "output": output,
            "room_id": destination.id,
        }

    if action == "inventory":
        return {"success": True, "output": f"Inventory: {', '.join(player.inventory) if player.inventory else 'empty'}"}

    if action == "take":
        target = command.get("target")
        if not target:
            return {"success": False, "output": "Take what?"}

        item = _find_item(world["items"], target)
        if item is None or not item.is_in_room(player.current_room_id):
            return {"success": False, "output": f"You do not see a {target} here."}

        item.take_by(player.id)
        player.inventory.append(item.id)
        return {"success": True, "output": f"You take the {item.name}."}

    if action == "drop":
        target = command.get("target")
        if not target:
            return {"success": False, "output": "Drop what?"}

        item = _find_item(world["items"], target)
        if item is None or item.id not in player.inventory or item.owned_by != player.id:
            return {"success": False, "output": f"You are not carrying a {target}."}

        was_lit = item.is_light_source and item.is_lit
        if was_lit:
            item.is_lit = False
        player.inventory.remove(item.id)
        item.drop_in(player.current_room_id)
        output = f"You drop the {item.name}."
        if was_lit:
            output += " It goes out."
        return {"success": True, "output": output}

    if action == "give":
        target = command.get("target")
        target_player_name = command.get("target_player")
        if not target or not target_player_name:
            return {
                "success": False,
                "output": "Usage: give <item> to <player>.",
            }

        recipient = next(
            (
                candidate
                for candidate in world["players"].values()
                if candidate.name.casefold() == target_player_name.casefold()
            ),
            None,
        )
        if recipient is None:
            return {"success": False, "output": f"{target_player_name} is not here."}
        if recipient.id == player.id:
            return {"success": False, "output": "You cannot give an item to yourself."}
        if recipient.current_room_id != player.current_room_id:
            return {"success": False, "output": f"{recipient.name} is not here."}

        item = _find_item(world["items"], target)
        if item is None or item.id not in player.inventory or item.owned_by != player.id:
            return {"success": False, "output": f"You are not carrying a {target}."}
        if item.is_light_source and item.is_lit:
            item.is_lit = False

        player.inventory.remove(item.id)
        recipient.inventory.append(item.id)
        item.take_by(recipient.id)
        return {
            "success": True,
            "output": f"You give the {item.name} to {recipient.name}.",
            "recipient_output": f"{player.name} gives you the {item.name}.",
            "recipient_id": recipient.id,
        }

    if action == "put":
        target = command.get("target")
        container_target = command.get("container")
        if not target or not container_target:
            return {"success": False, "output": "Usage: put <item> in <container>."}

        item = _find_item(world["items"], target)
        if item is None or item.id not in player.inventory or item.owned_by != player.id:
            return {"success": False, "output": f"You are not carrying a {target}."}

        container = _find_item(world["items"], container_target)
        if not _is_accessible(container, player):
            return {
                "success": False,
                "output": f"You do not see a {container_target} here.",
            }
        if item.id == container.id:
            return {"success": False, "output": f"You cannot put the {item.name} inside itself."}
        if not container.can_open:
            return {"success": False, "output": f"The {container.name} is not a container."}
        if not container.is_open:
            return {"success": False, "output": f"The {container.name} is closed."}
        if item.is_light_source and item.is_lit:
            return {
                "success": False,
                "output": (
                    f"You must extinguish the {item.name} before putting it "
                    f"in the {container.name}."
                ),
            }

        player.inventory.remove(item.id)
        item.put_in(container.id)
        return {
            "success": True,
            "output": f"You put the {item.name} in the {container.name}.",
        }

    if action == "take_from":
        target = command.get("target")
        container_target = command.get("container")
        if not target or not container_target:
            return {"success": False, "output": "Usage: take <item> from <container>."}

        container = _find_item(world["items"], container_target)
        if not _is_accessible(container, player):
            return {
                "success": False,
                "output": f"You do not see a {container_target} here.",
            }
        if not container.can_open:
            return {"success": False, "output": f"The {container.name} is not a container."}
        if not container.is_open:
            return {"success": False, "output": f"The {container.name} is closed."}

        item = _find_item(world["items"], target)
        if item is None or item.container_id != container.id:
            return {
                "success": False,
                "output": f"There is no {target} in the {container.name}.",
            }

        item.take_by(player.id)
        player.inventory.append(item.id)
        return {
            "success": True,
            "output": f"You take the {item.name} from the {container.name}.",
        }

    if action == "examine":
        target = command.get("target")
        if not target:
            return {"success": False, "output": "Examine what?"}

        item = _find_item(world["items"], target)
        item_is_accessible = _is_accessible(item, player)
        if not item_is_accessible:
            return {"success": False, "output": f"You do not see a {target} here."}

        output = item.description
        contains_items = any(
            contained_item.container_id == item.id
            for contained_item in world["items"].values()
        )
        if item.can_open and not item.is_open and contains_items:
            output += (
                " It seems heavier than you might expect, and something rattles "
                "inside when you shake it."
            )
        if item.is_light_source:
            light_description = (
                "Its flame flickers" if item.is_lit else "It is not lit"
            )
            if item.fuel_remaining is None:
                fuel_description = "does not require fuel"
            elif item.fuel_remaining == 0:
                fuel_description = "is out of fuel"
            elif item.fuel_remaining <= 5:
                fuel_description = "is running low on fuel"
            elif item.fuel_remaining <= 10:
                fuel_description = "has some fuel remaining"
            else:
                fuel_description = "has plenty of fuel remaining"
            output += f" {light_description} and {fuel_description}."

        return {"success": True, "output": output}

    if action in {"open", "close"}:
        target = command.get("target")
        verb = action.capitalize()
        if not target:
            return {"success": False, "output": f"{verb} what?"}

        item = _find_item(world["items"], target)
        item_is_accessible = _is_accessible(item, player)
        if not item_is_accessible:
            return {"success": False, "output": f"You do not see a {target} here."}
        if not item.can_open:
            return {"success": False, "output": f"The {item.name} cannot be opened."}
        if action == "open" and item.is_open:
            return {"success": False, "output": f"The {item.name} is already open."}
        if action == "close" and not item.is_open:
            return {"success": False, "output": f"The {item.name} is already closed."}

        item.is_open = action == "open"
        return {"success": True, "output": f"You {action} the {item.name}."}

    if action == "use":
        target = command.get("target")
        if not target:
            return {"success": False, "output": "Use what?"}

        item = _find_item(world["items"], target)
        if item is None or item.id not in player.inventory or item.owned_by != player.id:
            return {
                "success": False,
                "output": f"You need to be carrying the {target} to use it.",
            }
        if not item.can_use:
            return {"success": False, "output": f"The {item.name} cannot be used."}

        if item.is_light_source:
            if item.is_lit:
                return {"success": False, "output": f"The {item.name} is already lit."}
            if item.fuel_remaining == 0:
                return {"success": False, "output": f"The {item.name} is out of fuel."}
            item.is_lit = True

        return {"success": True, "output": item.use_message or f"You use the {item.name}."}

    if action == "extinguish":
        target = command.get("target")
        if not target:
            return {"success": False, "output": "Extinguish what?"}

        item = _find_item(world["items"], target)
        if item is None or item.id not in player.inventory or item.owned_by != player.id:
            return {
                "success": False,
                "output": f"You need to be carrying the {target} to extinguish it.",
            }
        if not item.is_light_source:
            return {"success": False, "output": f"The {item.name} is not a light source."}
        if not item.is_lit:
            return {"success": False, "output": f"The {item.name} is not lit."}

        item.is_lit = False
        return {"success": True, "output": f"You extinguish the {item.name}."}

    if action == "help":
        return {
            "success": True,
            "output": (
                "Available commands: look, north, south, east, west, inventory, "
                "take, take <item> from <container>, put <item> in <container>, "
                "look in <container>, "
                "drop, give <item> to <player>, say <message>, "
                "say to <player> <message>, tell <player> <message>, examine, "
                "who [page], open, close, use, extinguish, help\n"
                "Slash commands: /theme light | dark | techo; /debug on | off"
            ),
        }

    return {"success": False, "output": "Unknown command."}
