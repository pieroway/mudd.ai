"""Deterministic movement for carts on generated maze tracks."""

from app.domain.directions import HORIZONTAL, OPPOSITE, resolve_direction
from app.domain.item_context import total_weight, visible

CART = "vehicle_minecart"
SWITCH = "fixture_rail_switch"
HELP = "/rail status | switch <direction> | brake on|off | ride|push|pull <direction>"


def rail_routes(room, world):
    routes = {}
    for direction in room.conditions.get("rail", []):
        target = world["rooms"].get(room.exits.get(direction))
        if (target and target.exits.get(OPPOSITE[direction]) == room.id
                and OPPOSITE[direction] in target.conditions.get("rail", [])):
            routes[direction] = target.id
    return routes


def rail_items(template, room, player, world):
    return [
        item for item in world["items"].values()
        if item.template_id == template and item.room_id == room.id and visible(item, player, world)
    ]


def rail_description(room, player, world):
    routes = rail_routes(room, world)
    if not routes:
        return ""
    switches = rail_items(SWITCH, room, player, world)
    carts = rail_items(CART, room, player, world)
    role = "buffer stop" if len(routes) == 1 else "junction" if len(routes) > 2 else "track"
    directions = ", ".join(f"{direction} (incline)" if direction in {"up", "down"} else direction
                           for direction in sorted(routes))
    output = f"\nRail {role}: {directions}."
    if len(switches) == 1:
        alignment = switches[0].state.get("alignment")
        if alignment in routes:
            output += f" The switch is aligned {alignment}."
    if len(carts) == 1:
        brake = "applied" if carts[0].state.get("braked", True) else "released"
        output += f" The minecart brake is {brake}."
    elif carts:
        output += f" Minecarts here: {len(carts)}."
    return output


def execute_rail(arguments, player, world):
    def reply(output, success=False):
        return {"output": output, "success": success, "room_id": player.current_room_id}

    room = world["rooms"][player.current_room_id]
    routes = rail_routes(room, world)
    if arguments == ["status"]:
        status = rail_description(room, player, world)
        return reply(status.strip() if status else "There are no tracks here.", bool(status))
    if len(arguments) != 2:
        return reply(HELP)
    action, argument = arguments
    direction = resolve_direction(argument, player.facing_direction)
    switches = rail_items(SWITCH, room, player, world)
    switch = switches[0] if len(switches) == 1 else None
    if action == "switch":
        if switch is None or direction not in routes:
            return reply("Choose a connected direction at a railway switch.")
        if switch.condition.get("broken"):
            return reply("The railway switch is broken.")
        switch.state["alignment"] = direction
        return reply(f"You align the railway switch {direction}.", True)
    if action not in {"brake", "ride", "push", "pull"}:
        return reply(HELP)

    carts = rail_items(CART, room, player, world)
    occupied = player.state.get("occupied_item")
    cart = next((item for item in carts if item.id == occupied), None)
    if cart is None and len(carts) == 1 and not occupied:
        cart = carts[0]
    if cart is None:
        return reply("There is no unambiguous minecart here.")
    riders = cart.relationships.get("occupants", [])
    riding = occupied == cart.id and riders == [player.id]
    if riders and not riding:
        return reply("Another player occupies the minecart.")
    if action == "brake":
        if argument not in {"on", "off"}:
            return reply("Use /rail brake on or /rail brake off.")
        cart.state["braked"] = argument == "on"
        return reply(f"You {'apply' if argument == 'on' else 'release'} the minecart brake.", True)
    if (action == "ride") != riding:
        return reply("Board the minecart to ride it." if action == "ride" else "Leave the minecart first.")
    if cart.state.get("broken") or cart.condition.get("broken"):
        return reply("The minecart needs repairs.")
    if cart.state.get("braked", True):
        return reply("Release the minecart brake first.")
    if direction not in routes:
        return reply("There is no connected track in that direction.")
    if len(routes) > 2 and switch is None:
        return reply("A usable railway switch is required at this junction.")
    if switch and (switch.condition.get("broken") or switch.state.get("alignment") != direction):
        return reply("The railway switch is broken or aligned with a different track.")
    if direction == "up" and riding:
        return reply("The minecart cannot coast uphill. Leave it and push or pull it up the incline.")
    if direction in room.doors and not room.doors[direction].is_open:
        return reply("A closed door blocks the track.")
    destination = routes[direction]
    items = world["items"]
    if any(item.template_id == CART and item.room_id == destination for item in items.values()):
        return reply("Another minecart blocks the track.")
    cargo = sum(total_weight(item, items) for item in items.values() if item.container_id == cart.id)
    if riding:
        cargo += player.state.get("body_weight_kg", 75) + sum(
            total_weight(item, items) for item in items.values() if item.owned_by == player.id
        )
    if cargo > cart.capabilities["container"]["maximum_weight_kg"]:
        return reply("The minecart is overloaded.")
    cart.room_id = destination
    player.move(destination)
    if direction in HORIZONTAL:
        player.facing_direction = direction
    return reply(f"You {action} the minecart {direction} to {world['rooms'][destination].name}.", True)
