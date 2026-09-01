from __future__ import annotations


def execute_command(command, player, world):
    """Execute a parsed command against a deterministic test world."""
    action = command.get("action")

    if action == "look":
        room = world["rooms"][player.current_room_id]
        return {"success": True, "output": room.look(), "room_id": room.id}

    if action == "move":
        direction = command.get("direction")
        room = world["rooms"][player.current_room_id]
        next_room_id = room.exits.get(direction)
        if not next_room_id:
            return {"success": False, "output": f"You cannot go {direction} from here.", "room_id": room.id}

        player.move(next_room_id)
        destination = world["rooms"][next_room_id]
        return {
            "success": True,
            "output": f"You move {direction}.\n{destination.look()}",
            "room_id": destination.id,
        }

    if action == "inventory":
        return {"success": True, "output": f"Inventory: {', '.join(player.inventory) if player.inventory else 'empty'}"}

    if action == "help":
        return {
            "success": True,
            "output": "Available commands: look, north, south, east, west, inventory, help",
        }

    return {"success": False, "output": "Unknown command."}
