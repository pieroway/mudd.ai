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
        return {"success": True, "output": room.look(items_here), "room_id": room.id}

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
        return {
            "success": True,
            "output": f"You move {direction}.\n{destination.look(items_here)}",
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

        player.inventory.remove(item.id)
        item.drop_in(player.current_room_id)
        return {"success": True, "output": f"You drop the {item.name}."}

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

        return {"success": True, "output": item.description}

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

        return {"success": True, "output": item.use_message or f"You use the {item.name}."}

    if action == "help":
        return {
            "success": True,
            "output": (
                "Available commands: look, north, south, east, west, inventory, "
                "take, take <item> from <container>, put <item> in <container>, "
                "look in <container>, "
                "drop, examine, open, close, use, help\n"
                "Slash commands: /theme light | dark | techo"
            ),
        }

    return {"success": False, "output": "Unknown command."}
