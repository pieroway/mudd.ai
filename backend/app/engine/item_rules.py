"""Capability rules for template-backed objects; no AI decisions or executable effects."""

from copy import deepcopy
from uuid import uuid4

from app.domain.item_context import (
    describe,
    find_item,
    has_light,
    root,
    total_weight,
    visible,
    volume,
)

ITEM_MUTATIONS = frozenset(
    {
        "hold",
        "release",
        "wear",
        "wield",
        "remove",
        "search",
        "look_under",
        "lock",
        "unlock",
        "pick_lock",
        "read",
        "push",
        "pull",
        "move_object",
        "break",
        "repair",
        "light",
        "attach",
        "detach",
        "tie",
        "untie",
        "climb",
        "sit",
        "lie",
        "board",
        "leave",
        "pour",
        "fill",
        "fold",
        "unfold",
        "switch",
        "split",
        "combine",
        "spend",
        "consume",
        "dig",
        "harvest",
        "throw",
        "pry",
        "cut",
        "slash",
        "stab",
        "pilot",
        "launch",
        "beach",
    }
)


def result(text, success=False):
    return {"success": success, "output": text}


def carried_weight(player, world):
    return sum(
        total_weight(item, world["items"])
        for item in world["items"].values()
        if item.owned_by == player.id
    )


def carry_error(item, player, world):
    origin = root(item, world["items"])
    if origin and origin.owned_by == player.id:
        return None
    if carried_weight(player, world) + total_weight(item, world["items"]) > player.state.get(
        "carrying_capacity_kg", 40
    ):
        return "That would exceed your carrying capacity."
    return None


def placement_error(item, parent, player, world, placement="contained_in"):
    if item.id == parent.id:
        return "An object cannot contain or support itself."
    current = parent
    seen = set()
    while current:
        if current.id == item.id or current.id in seen:
            return "That placement would create a containment cycle."
        seen.add(current.id)
        current = world["items"].get(current.container_id)
    cap = "surface" if placement == "resting_on" else "container"
    settings = parent.capabilities.get(cap)
    if settings is None:
        return f"The {parent.name} is not a {cap}."
    if placement == "contained_in" and parent.can_open and not parent.is_open:
        return f"The {parent.name} is closed."
    if parent.state.get("locked"):
        return f"The {parent.name} is locked."
    children = [
        child
        for child in world["items"].values()
        if child.container_id == parent.id and child.id != item.id
    ]
    weight = total_weight(item, world["items"]) + sum(
        total_weight(child, world["items"]) for child in children
    )
    if weight > settings.get("maximum_weight_kg", float("inf")):
        return f"The {parent.name} cannot support that much weight."
    if cap == "container":
        if sum(volume(child) for child in children) + volume(item) > settings.get(
            "capacity_litres", float("inf")
        ):
            return f"The {item.name} will not fit inside the {parent.name}."
        opening = settings.get("opening_width_cm")
        width = item.dimensions_cm.get("width") or {
            "tiny": 1,
            "small": 5,
            "medium": 15,
            "large": 45,
            "huge": 100,
        }.get(item.size, 1)
        if opening and width > opening:
            return f"The {item.name} will not fit through the opening of the {parent.name}."
        permitted = settings.get("permitted_contents")
        if permitted and not set(item.categories) & set(permitted):
            return f"The {parent.name} cannot hold that kind of object."
    current = parent
    while current.container_id:
        ancestor = world["items"][current.container_id]
        support = (
            "surface" if current.relationships.get("placement") == "resting_on" else "container"
        )
        limit = ancestor.capabilities.get(support, {}).get("maximum_weight_kg", float("inf"))
        load = sum(
            total_weight(child, world["items"])
            for child in world["items"].values()
            if child.container_id == ancestor.id
        )
        if load + total_weight(item, world["items"]) > limit:
            return f"The {ancestor.name} cannot support that much weight."
        current = ancestor
    return None


def discover(parent, player, world):
    found = []
    for child in world["items"].values():
        if child.container_id != parent.id:
            continue
        if child.relationships.get("placement") not in {"hidden_under", "covered_by"}:
            if not parent.is_open:
                continue
        if child.discovery.get("hidden") and player.id not in child.discovery.get(
            "discovered_by", []
        ):
            child.discovery.setdefault("discovered_by", []).append(player.id)
            found.append(child.name)
    return found


def free_slots(player, world):
    used = {
        item.relationships.get("slot")
        for item in world["items"].values()
        if item.owned_by == player.id
    }
    if "both_hands" in used:
        return []
    return [slot for slot in ("right_hand", "left_hand") if slot not in used]


def check_tool(command, player, world, action):
    tool = find_item(command.get("tool"), player, world, owned=True)
    if tool is None:
        return None, "You need an accessible tool in your inventory."
    if tool.state.get("broken") or tool.condition.get("broken"):
        return None, f"The {tool.name} is broken."
    actions = tool.capabilities.get("usable", {}).get("actions", [])
    if action not in actions:
        return None, f"The {tool.name} cannot be used to {action}."
    if not tool.relationships.get("slot") and len(
        free_slots(player, world)
    ) < tool.capabilities.get("holdable", {}).get("required_hands", 1):
        return None, "Your hands are full."
    return tool, None


def execute_item_command(command, player, world):
    action = command.get("action")
    items = world["items"]
    item = find_item(command.get("target"), player, world)
    parent = find_item(command.get("container"), player, world)
    tool = find_item(command.get("tool"), player, world)
    typed = any(candidate and candidate.template_id for candidate in (item, parent, tool))
    if action == "use" and item and item.template_id and item.is_light_source:
        action = "light"
    if action == "interact" and typed and item and tool:
        actions = tool.capabilities.get("usable", {}).get("actions", [])
        if item.relationships.get("lock_id") in tool.relationships.get("opens", []):
            action = "unlock"
        else:
            action = next(
                (
                    verb
                    for verb, cap in [
                        ("pry", "pryable"),
                        ("repair", "repairable"),
                        ("ignite", "lightable"),
                        ("cut", "breakable"),
                        ("break", "breakable"),
                    ]
                    if verb in actions and item.has_capability(cap)
                ),
                "interact",
            )
            if action == "ignite":
                action = "light"
    if action == "look" and (
        any(obj.template_id and visible(obj, player, world) for obj in items.values())
        or not has_light(player, world)
    ):
        room = world["rooms"][player.current_room_id]
        if not has_light(player, world):
            return {
                "success": True,
                "output": "It is too dark to make out your surroundings.",
                "room_id": room.id,
            }
        here = [
            obj for obj in items.values() if obj.room_id == room.id and visible(obj, player, world)
        ]
        text = room.look([obj.name for obj in here]) + f"\nFacing: {player.facing_direction}."
        if room.exits and any(
            obj.is_light_source
            and obj.is_lit
            and root(obj, items)
            and root(obj, items).owned_by == player.id
            and visible(obj, player, world)
            for obj in items.values()
        ):
            distant = ", ".join(
                f"{direction}: {world['rooms'][destination].name}"
                for direction, destination in sorted(room.exits.items())
            )
            text += f"\nTorchlight reaches farther. Beyond the exits: {distant}."
        descriptions = [describe(obj, player, world, "room") for obj in here if obj.template_id]
        return {
            "success": True,
            "output": text + ("\n" + "\n".join(descriptions) if descriptions else ""),
            "room_id": room.id,
        }
    if action == "inventory" and any(
        obj.template_id and obj.owned_by == player.id for obj in items.values()
    ):
        entries = [
            describe(obj, player, world, "inventory")
            for obj in items.values()
            if obj.owned_by == player.id and visible(obj, player, world)
        ]
        return result("Inventory:\n" + "\n".join(entries), True)
    if action == "examine" and not item:
        other = next(
            (
                candidate
                for candidate in world.get("players", {}).values()
                if candidate.name.casefold() == str(command.get("target")).casefold()
                and candidate.current_room_id == player.current_room_id
            ),
            None,
        )
        if other and has_light(player, world):
            equipment = [
                obj
                for obj in items.values()
                if obj.owned_by == other.id
                and obj.relationships.get("slot")
                and not obj.discovery.get("hidden")
            ]
            return result(
                "\n".join(
                    [
                        f"{other.name} is here.",
                        *(describe(obj, player, world, "other") for obj in equipment),
                    ]
                ),
                True,
            )
    if action not in ITEM_MUTATIONS and action not in {"look_on", "consume"} and not typed:
        return None
    if action in {"search", "look_under"} and str(command.get("target")).casefold() in {
        "room",
        "here",
        "around",
    }:
        if not has_light(player, world):
            return result("It is too dark to search here.")
        found = []
        for obj in items.values():
            if obj.room_id == player.current_room_id:
                if obj.discovery.get("hidden"):
                    if player.id not in obj.discovery.get("discovered_by", []):
                        obj.discovery.setdefault("discovered_by", []).append(player.id)
                    found.append(obj.name)
                elif obj.has_capability("searchable"):
                    clue = obj.discovery.get("clue")
                    if clue:
                        found.append(str(clue))
        return result(
            "You search the room. "
            + (
                "You notice: " + ", ".join(found) + "."
                if found
                else "Nothing unusual catches your eye."
            ),
            True,
        )
    if action == "leave":
        occupied = player.state.get("occupied_item")
        if not occupied:
            return result("You are not occupying an object.")
        obj = items.get(occupied)
        if obj:
            obj.relationships["occupants"] = [
                pid for pid in obj.relationships.get("occupants", []) if pid != player.id
            ]
        player.state.pop("occupied_item", None)
        player.state.pop("posture", None)
        return result("You leave your place.", True)
    if action == "pick_lock" and not command.get("tool"):
        tool = next(
            (
                obj
                for obj in items.values()
                if obj.owned_by == player.id
                and "pick_lock" in obj.capabilities.get("usable", {}).get("actions", [])
            ),
            None,
        )
    if item is None and action in {"look_in", "look_on"}:
        item = parent
    if item is None:
        return result(
            "You cannot see that object here. Use its full name if several objects match."
        )
    if (item.state.get("broken") or item.condition.get("broken")) and action in {
        "wield",
        "light",
        "climb",
        "fill",
        "pour",
        "use",
        "consume",
        "attach",
        "tie",
        "board",
        "sit",
        "lie",
        "switch",
        "pilot",
        "launch",
    }:
        return result(f"The {item.name} is broken; repair it first.")
    if (
        not typed
        and tool
        and tool.interaction_target_id == item.id
        and action in {"unlock", "repair", "light", "read", "interact"}
    ):
        return None
    if action in {"take", "take_from"}:
        if item.owned_by == player.id:
            return result(f"You already carry the {item.name}.")
        if action == "take_from" and (parent is None or item.container_id != parent.id):
            return result("That object is not in the specified container.")
        if not item.portable or (item.template_id and not item.has_capability("takeable")):
            return result(f"The {item.name} is too large or fixed in place to carry.")
        if (
            item.relationships.get("attached_to")
            or item.relationships.get("occupants")
            or any(obj.relationships.get("attached_to") == item.id for obj in items.values())
        ):
            return result(f"Detach or vacate the {item.name} first.")
        error = carry_error(item, player, world)
        if error:
            return result(error)
        item.take_by(player.id)
        item.relationships.setdefault("owner", player.id)
        if item.id not in player.inventory:
            player.inventory.append(item.id)
        return result(f"You take the {item.name}.", True)
    if action in {"hold", "wield", "wear"}:
        if item.owned_by != player.id:
            return result(f"Take the {item.name} into your inventory first.")
        cap = {"hold": "holdable", "wield": "wieldable", "wear": "wearable"}[action]
        if not item.has_capability(cap) and (action != "hold" or not item.portable):
            return result(f"The {item.name} cannot be {action}ed.")
        slots = free_slots(player, world)
        if action == "wield":
            allowed = item.capabilities["wieldable"].get("slots", ["left_hand", "right_hand"])
            slots = [slot for slot in slots if slot in allowed]
        requested = command.get("slot")
        if action == "wear":
            allowed = item.capabilities.get(cap, {}).get("slots", [])
            used = {
                obj.relationships.get("slot")
                for obj in items.values()
                if obj.owned_by == player.id and obj.id != item.id
            }
            slots = [slot for slot in allowed if slot not in used]
        required = item.capabilities.get("holdable", {}).get("required_hands", 1)
        if action != "wear" and required == 2:
            slots = ["both_hands"] if len(slots) == 2 else []
        if requested:
            slots = [slot for slot in slots if slot == requested]
        if not slots:
            return result("Your hands or the required equipment slot are full.")
        item.relationships.update(
            {
                "slot": slots[0],
                "equipment": {"hold": "held", "wield": "wielded", "wear": "worn"}[action],
            }
        )
        return result(describe(item, player, world, "inventory"), True)
    if action in {"release", "remove"}:
        if item.owned_by != player.id or not item.relationships.get("slot"):
            return result("You are not holding or wearing that object.")
        item.relationships.pop("slot", None)
        item.relationships.pop("equipment", None)
        return result(f"You return the {item.name} to your inventory.", True)
    if action == "put":
        if item.owned_by != player.id or parent is None:
            return result("You must carry the object and be able to reach its destination.")
        if any(obj.relationships.get("attached_to") == item.id for obj in items.values()):
            return result("Detach connected objects before placing the anchor elsewhere.")
        placement = command.get("placement") or "contained_in"
        error = placement_error(item, parent, player, world, placement)
        if error:
            return result(error)
        if item.is_lit:
            return result(f"Extinguish the {item.name} first.")
        item.put_in(parent.id)
        item.relationships["placement"] = placement
        player.inventory.remove(item.id)
        return result(
            f'You put the {item.name} {"on" if placement == "resting_on" else "in"} the {parent.name}.',
            True,
        )
    if action in {"look_in", "look_on"}:
        placement = "resting_on" if action == "look_on" else "contained_in"
        cap = "surface" if action == "look_on" else "container"
        if not item.has_capability(cap):
            return result(f"The {item.name} is not a {cap}.")
        if placement == "contained_in" and item.can_open and not item.is_open:
            return result(f"The {item.name} is closed.")
        children = [
            describe(obj, player, world, "contents")
            for obj in items.values()
            if obj.container_id == item.id
            and obj.relationships.get("placement", "contained_in") == placement
            and visible(obj, player, world)
        ]
        return result("\n".join(children) if children else f"The {item.name} is empty.", True)
    if action == "examine":
        return result(describe(item, player, world), True)
    if action in {"open", "close"}:
        if not free_slots(player, world) and not item.relationships.get("slot"):
            return result("Your hands are full.")
        if not item.can_open:
            return result(f"The {item.name} cannot be opened.")
        if action == "open" and item.state.get("locked"):
            return result(f"The {item.name} is locked.")
        opened = action == "open"
        if item.is_open == opened:
            return result(f'The {item.name} is already {"open" if opened else "closed"}.')
        item.is_open = opened
        item.state["open"] = opened
        return result(f"You {action} the {item.name}.", True)
    if action in {"lock", "unlock", "pick_lock"}:
        if not item.has_capability("lockable") or not item.relationships.get("lock_id"):
            return result(f"The {item.name} has no usable lock.")
        if action == "lock" and item.is_open:
            return result(f"Close the {item.name} first.")
        locked = action == "lock"
        if bool(item.state.get("locked")) == locked:
            return result(f'The {item.name} is already {"locked" if locked else "unlocked"}.')
        if action == "pick_lock":
            if (
                not item.capabilities["lockable"].get("pickable")
                or tool is None
                or tool.owned_by != player.id
                or "pick_lock" not in tool.capabilities.get("usable", {}).get("actions", [])
                or tool.state.get("broken")
            ):
                return result("You need a suitable lockpick, and this lock must support picking.")
            if player.state.get("lockpicking", 5) + tool.capabilities.get("usable", {}).get(
                "skill_bonus", 0
            ) < item.capabilities["lockable"].get("difficulty", 10):
                return result("This lock is beyond your lock-picking skill.")
        elif (
            tool is None
            or tool.owned_by != player.id
            or item.relationships["lock_id"] not in tool.relationships.get("opens", [])
            or tool.state.get("broken")
        ):
            return result("You need the matching key in your inventory.")
        item.state["locked"] = locked
        return result(
            f'You {"pick the lock on" if action == "pick_lock" else action} the {item.name}.', True
        )
    if action in {"search", "look_under", "pry", "push", "pull", "move_object"}:
        cap = (
            "searchable"
            if action in {"search", "look_under"}
            else "pryable" if action == "pry" else "movable"
        )
        if not item.has_capability(cap):
            return result(f"The {item.name} does not support that interaction.")
        if action == "pry":
            _, error = check_tool(command, player, world, "pry")
            if error:
                return result(error)
            if item.state.get("locked"):
                return result("The object is locked; unlock it or use an explicit breaking action.")
            if item.can_open:
                item.is_open = True
                item.state["open"] = True
        if player.state.get("strength", 15) < item.capabilities.get(cap, {}).get(
            "strength_required", 0
        ):
            return result(f"The {item.name} is too heavy for you to move.")
        if item.relationships.get("occupants"):
            return result(f"The {item.name} is occupied.")
        found = discover(item, player, world)
        if action not in {"search", "look_under"}:
            item.state["shifted"] = True
        return result(
            f'You {"search" if action == "look_under" else action.replace("_object", "")} the {item.name}. '
            + ("You discover: " + ", ".join(found) + "." if found else "Nothing else is revealed."),
            True,
        )
    if action == "read":
        if not item.has_capability("readable"):
            return result(f"There is nothing readable on the {item.name}.")
        language = item.capabilities["readable"].get("requires_language", "common")
        if language not in player.state.get("languages", ["common"]):
            return result("You cannot read this language.")
        if item.can_open and not item.is_open:
            return result(f"Open the {item.name} first.")
        part = command.get("part", "text")
        content = item.state.get("readable", {})
        return result(str(content.get(part, "The writing is blank or illegible.")), True)
    if action in {"light", "extinguish"}:
        if not item.is_light_source:
            return result(f"The {item.name} is not a light source.")
        lit = action == "light"
        if item.is_lit == lit:
            return result(f'The {item.name} is already {"lit" if lit else "unlit"}.')
        if lit:
            if item.fuel_remaining == 0:
                return result(f"The {item.name} is out of fuel.")
            if item.state.get("wet"):
                return result(f"The {item.name} is too wet to light.")
            if item.capabilities.get("lightable", {}).get("requires_ignition_source"):
                ignition = tool or next(
                    (
                        obj
                        for obj in items.values()
                        if obj.owned_by == player.id
                        and (obj.is_lit or obj.template_id == "tool_flint_steel")
                    ),
                    None,
                )
                if (
                    ignition is None
                    or ignition.owned_by != player.id
                    or not (
                        ignition.is_lit
                        or ignition.template_id == "tool_flint_steel"
                        or "ignite" in ignition.capabilities.get("usable", {}).get("actions", [])
                    )
                ):
                    return result("You need an ignition source in your inventory.")
        item.is_lit = lit
        item.state["lit"] = lit
        return result(f"You {action} the {item.name}.", True)
    if action in {"break", "repair", "cut", "slash", "stab"}:
        damaging = action != "repair"
        cap = "breakable" if damaging else "repairable"
        if not item.has_capability(cap):
            return result(f"The {item.name} cannot be {action}ed.")
        _, error = check_tool(command, player, world, action)
        if error:
            return result(error)
        if damaging:
            power = tool.capabilities.get("usable", {}).get("power", 10)
            if power < item.capabilities["breakable"].get("hardness", 0):
                return result("Your tool cannot overcome the material hardness.")
            item.durability = max(0, (item.durability or 0) - power)
            if item.durability == 0:
                item.state["broken"] = True
                item.condition["broken"] = True
                item.state["locked"] = False
                if item.can_open:
                    item.is_open = True
                    item.state["open"] = True
        else:
            item.durability = item.maximum_durability
            item.state["broken"] = False
            item.condition["broken"] = False
        return result(f"You {action} the {item.name}.", True)
    if action in {"use", "consume"}:
        if item.owned_by != player.id:
            return result("Take the object out of its container first.")
        if item.state.get("broken"):
            return result(f"The {item.name} is broken.")
        effect = item.capabilities.get("consumable")
        if effect:
            if effect.get("effect") not in {"heal", "nourish", "antidote"}:
                return result("This object has no supported effect.")
            if not free_slots(player, world) and not item.relationships.get("slot"):
                return result("Your hands are full.")
            if any(child.container_id == item.id for child in items.values()):
                return result("Empty the object before consuming it.")
            if effect.get("effect") == "heal":
                player.state["health"] = min(
                    player.state.get("maximum_health", 100),
                    player.state.get("health", 100) + effect.get("amount", 0),
                )
            elif effect.get("effect") == "nourish":
                player.state["nourishment"] = min(
                    100, player.state.get("nourishment", 50) + effect.get("amount", 0)
                )
            if effect.get("effect") == "antidote":
                player.state["poisoned"] = False
            if item.quantity > 1:
                item.quantity -= 1
            else:
                del items[item.id]
                player.inventory.remove(item.id)
            return result(f"You consume the {item.name}.", True)
        return result("Specify a supported action and target for this object.")
    if action in {"attach", "tie"}:
        target = find_item(command.get("destination"), player, world)
        cap = "tieable" if action == "tie" else "attachable"
        if (
            not item.has_capability(cap)
            or target is None
            or not target.has_capability("attachable")
        ):
            return result("You need a carried attachment and a suitable reachable anchor.")
        if item.id == target.id:
            return result("An object cannot attach to itself.")
        if item.relationships.get("attached_to"):
            return result("Detach the existing attachment first.")
        mooring = not item.portable and item.has_capability("enterable")
        if mooring:
            if tool is None or tool.owned_by != player.id or not tool.has_capability("tieable"):
                return result("Use a carried rope to moor the vessel.")
            if tool.relationships.get("attached_to"):
                return result("Detach the rope before using it to moor another object.")
        elif item.owned_by != player.id:
            return result("Carry the attachment before securing it.")
        allowed = item.capabilities.get(cap, {}).get("compatible_targets")
        if allowed and not (
            set(allowed) & set(target.categories) or target.capabilities["attachable"].get("secure")
        ):
            return result("These objects are not compatible attachments.")
        if mooring:
            tool.drop_in(player.current_room_id)
            player.inventory.remove(tool.id)
            tool.relationships["attached_to"] = item.id
            tool.state["tied"] = True
            item.relationships["tied_with"] = tool.id
        else:
            item.drop_in(player.current_room_id)
            player.inventory.remove(item.id)
        item.relationships["attached_to"] = target.id
        item.state["tied"] = action == "tie"
        return result(f"You {action} the {item.name} to the {target.name}.", True)
    if action in {"detach", "untie"}:
        if not item.relationships.get("attached_to"):
            return result("That object is not attached.")
        if item.relationships.get("occupants"):
            return result("Someone is using that attachment.")
        item.relationships.pop("attached_to", None)
        rope = items.get(item.relationships.pop("tied_with", None))
        if rope:
            rope.relationships.pop("attached_to", None)
            rope.state["tied"] = False
        item.state["tied"] = False
        return result(f"You {action} the {item.name}.", True)
    if action == "climb":
        settings = item.capabilities.get("climbable")
        if settings is None:
            return result("You cannot climb that object.")
        anchor = items.get(item.relationships.get("attached_to"))
        if settings.get("requires_secure_attachment") and (
            not anchor or not anchor.capabilities.get("attachable", {}).get("secure")
        ):
            return result("Secure the rope before climbing it.")
        load = player.state.get("body_weight_kg", 75) + carried_weight(player, world)
        if load > min(
            settings.get("maximum_load_kg", 0),
            (
                anchor.capabilities.get("attachable", {}).get("maximum_load_kg", 0)
                if anchor
                else float("inf")
            ),
        ):
            return result("The attachment cannot support your weight.")
        destination = item.relationships.get("climb_destination")
        if (
            destination not in world["rooms"]
            or destination not in world["rooms"][player.current_room_id].exits.values()
        ):
            return result("The rope is secure, but it does not lead to a reachable exit.")
        room = world["rooms"][player.current_room_id]
        if any(
            room.exits.get(direction) == destination and not door.is_open
            for direction, door in room.doors.items()
        ):
            return result("Open the door at that exit before climbing through it.")
        player.move(destination)
        return result(f"You climb the {item.name}.", True)
    if action in {"sit", "lie", "board"}:
        cap = {"sit": "sittable", "lie": "lieable", "board": "enterable"}[action]
        if not item.has_capability(cap):
            return result("That object cannot support this activity.")
        if player.state.get("occupied_item"):
            return result("Leave your current place first.")
        occupants = item.relationships.setdefault("occupants", [])
        if len(occupants) >= item.capabilities[cap].get("maximum_occupants", 1):
            return result("There is no room for another occupant.")
        maximum_load = item.capabilities.get("container", {}).get("maximum_weight_kg", float("inf"))
        cargo = sum(
            total_weight(child, items) for child in items.values() if child.container_id == item.id
        )
        if (
            cargo
            + carried_weight(player, world)
            + player.state.get("body_weight_kg", 75)
            + len(occupants) * 75
            > maximum_load
        ):
            return result("The object cannot support that load.")
        occupants.append(player.id)
        player.state.update({"occupied_item": item.id, "posture": action})
        return result(f"You {action} the {item.name}.", True)
    if action in {"pilot", "launch", "beach"}:
        settings = item.capabilities.get("pilotable")
        if settings is None:
            return result("This object is not a pilotable vessel.")
        room = world["rooms"][player.current_room_id]
        terrain = room.conditions.get("terrain", "land")
        if terrain not in settings.get("environments", []):
            return result("There is no suitable water here.")
        if item.state.get("tied") or item.relationships.get("attached_to"):
            return result("Untie the vessel before moving it.")
        if action == "launch":
            if item.state.get("afloat"):
                return result("The vessel is already afloat.")
            item.state["afloat"] = True
            return result(f"You launch the {item.name}.", True)
        if action == "beach":
            if not room.conditions.get("shore"):
                return result("There is no safe shore here.")
            item.state["afloat"] = False
            return result(f"You beach the {item.name}.", True)
        if player.state.get("occupied_item") != item.id or not item.state.get("afloat"):
            return result("Board and launch the vessel first.")
        if len(item.relationships.get("occupants", [])) > 1:
            return result("Travel with multiple occupants requires a coordinated group action.")
        if not any(
            obj.owned_by == player.id
            and "paddle" in obj.capabilities.get("usable", {}).get("actions", [])
            and not obj.state.get("broken")
            for obj in items.values()
        ):
            return result("You need a usable paddle or suitable oak staff in your inventory.")
        direction = command.get("direction")
        destination = room.exits.get(direction)
        if (
            destination not in world["rooms"]
            or world["rooms"][destination].conditions.get("terrain") not in settings["environments"]
        ):
            return result("That exit does not lead to a navigable water route.")
        if direction in room.doors and not room.doors[direction].is_open:
            return result("The route is blocked by a closed door.")
        item.room_id = destination
        player.move(destination)
        player.facing_direction = direction
        return result(f"You pilot the {item.name} {direction}.", True)
    if action in {"fill", "pour"}:
        target = find_item(command.get("destination"), player, world)
        if item.can_open and not item.is_open:
            return result(f"Open the {item.name} first.")
        if action == "fill":
            source, vessel = target, item
        else:
            source, vessel = item, target
        if (
            source is None
            or vessel is None
            or not source.has_capability("pourable")
            or not vessel.has_capability("fillable")
        ):
            return result("You need a liquid source and a compatible vessel.")
        if source.id == vessel.id:
            return result("An object cannot pour into itself.")
        if source.can_open and not source.is_open or vessel.can_open and not vessel.is_open:
            return result("Open both vessels first.")
        available = source.state.get("liquid_litres", 0)
        amount = min(
            available,
            vessel.capabilities["fillable"].get("capacity_litres", 0)
            - vessel.state.get("liquid_litres", 0),
        )
        if amount <= 0:
            return result("The source is empty or the destination is full.")
        if vessel.state.get("liquid_litres", 0) and vessel.state.get("liquid") != source.state.get(
            "liquid"
        ):
            return result("Empty the vessel before mixing different liquids.")
        vessel_root = root(vessel, items)
        source_root = root(source, items)
        if vessel_root.owned_by == player.id and source_root.owned_by != player.id:
            if carried_weight(player, world) + amount > player.state.get(
                "carrying_capacity_kg", 40
            ):
                return result("That liquid would exceed your carrying capacity.")
        source_ancestors = set()
        current = source
        while current:
            source_ancestors.add(current.id)
            current = items.get(current.container_id)
        current = vessel
        while current:
            contents = [child for child in items.values() if child.container_id == current.id]
            capacity = current.capabilities.get(
                "container", current.capabilities.get("surface", {})
            )
            delta = 0 if current.id in source_ancestors else amount
            load = sum(total_weight(child, items) for child in contents) + current.state.get(
                "liquid_litres", 0
            )
            if load + delta > capacity.get("maximum_weight_kg", float("inf")):
                return result(f"The {current.name} cannot support the added liquid weight.")
            if current.id == vessel.id and (
                sum(volume(child) for child in contents)
                + current.state.get("liquid_litres", 0)
                + amount
                > capacity.get("capacity_litres", float("inf"))
            ):
                return result(f"The {current.name} has no room for that much liquid.")
            current = items.get(current.container_id)
        vessel.state["liquid"] = source.state.get("liquid", "water")
        vessel.state["liquid_litres"] = vessel.state.get("liquid_litres", 0) + amount
        source.state["liquid_litres"] = available - amount
        return result(f"You transfer {amount:g} litres into the {vessel.name}.", True)
    if action in {"give", "spend"} and command.get("quantity") is not None:
        amount = command["quantity"]
        recipient = next(
            (
                candidate
                for candidate in world.get("players", {}).values()
                if candidate.name.casefold() == str(command.get("target_player")).casefold()
                and candidate.current_room_id == player.current_room_id
            ),
            None,
        )
        if recipient is None or recipient.id == player.id:
            return result("Choose another player in this room.")
        if (
            item.owned_by != player.id
            or not item.has_capability("stackable")
            or not isinstance(amount, int)
            or amount < 1
            or amount > item.quantity
        ):
            return result("You do not carry that quantity in a stack.")
        clone = deepcopy(item)
        clone.id = str(uuid4())
        clone.quantity = amount
        error = carry_error(clone, recipient, world)
        if error:
            return result("The recipient cannot carry that much weight.")
        if amount == item.quantity:
            clone = item
            player.inventory.remove(item.id)
        else:
            item.quantity -= amount
        clone.take_by(recipient.id)
        clone.relationships["owner"] = recipient.id
        items[clone.id] = clone
        recipient.inventory.append(clone.id)
        verb = "pay" if action == "spend" else "give"
        return {
            "success": True,
            "output": f"You {verb} {amount} {item.name} to {recipient.name}.",
            "recipient_id": recipient.id,
            "recipient_output": f"{player.name} gives you {amount} {item.name}.",
        }
    if action in {"split", "combine", "spend"}:
        if item.owned_by != player.id or not item.has_capability("stackable") or item.container_id:
            return result("You need a stack in your inventory.")
        amount = command.get("quantity", 0)
        if action == "combine":
            target = find_item(command.get("destination"), player, world, owned=True)
            if (
                target is None
                or target.id == item.id
                or target.template_id != item.template_id
                or target.state != item.state
                or target.relationships != item.relationships
            ):
                return result(
                    "Only matching stacks with the same state and relationships can combine."
                )
            if item.quantity + target.quantity > item.capabilities["stackable"].get(
                "maximum_quantity", 1000000
            ):
                return result("That stack would be too large.")
            if any(child.container_id in {item.id, target.id} for child in items.values()):
                return result("Stacks containing objects cannot combine.")
            item.quantity += target.quantity
            del items[target.id]
            player.inventory.remove(target.id)
            return result(f"You combine the stacks: {item.quantity} {item.name}.", True)
        if (
            not isinstance(amount, int)
            or amount < 1
            or amount >= item.quantity
            and action == "split"
            or amount > item.quantity
        ):
            return result("Choose a positive quantity within the stack.")
        if action == "spend":
            return result(
                "Spending requires an explicit supported recipient or transaction; no currency was removed."
            )
        clone = deepcopy(item)
        clone.id = str(uuid4())
        clone.quantity = amount
        item.quantity -= amount
        clone.relationships.pop("slot", None)
        clone.relationships.pop("equipment", None)
        items[clone.id] = clone
        player.inventory.append(clone.id)
        return result(f"You split off {amount} {item.name}.", True)
    if action in {"fold", "unfold", "switch"}:
        cap = "switchable" if action == "switch" else "foldable"
        if not item.has_capability(cap):
            return result("That object does not support this action.")
        item.state["active" if action == "switch" else "folded"] = (
            not item.state.get("active", False) if action == "switch" else action == "fold"
        )
        return result(f"You {action} the {item.name}.", True)
    if action in {"dig", "harvest", "throw"}:
        capability = {"dig": "diggable", "harvest": "harvestable", "throw": "throwable"}[action]
        if not item.has_capability(capability):
            return result("That object does not support this action.")
        if action == "throw":
            if item.owned_by != player.id:
                return result("You must carry an object before throwing it.")
            if item.relationships.get("attached_to"):
                return result("Detach the object before throwing it.")
            item.drop_in(player.current_room_id)
            player.inventory.remove(item.id)
        else:
            _, error = check_tool(command, player, world, action)
            if error:
                return result(error)
            if item.state.get("harvested") and action == "harvest":
                return result("Nothing is left to harvest.")
            item.state["dug" if action == "dig" else "harvested"] = True
            discover(item, player, world)
        return result(f"You {action} the {item.name}.", True)
    if action in {"drop", "give"}:
        if (
            item.relationships.get("attached_to")
            or item.relationships.get("occupants")
            or any(obj.relationships.get("attached_to") == item.id for obj in items.values())
        ):
            return result("Detach or vacate that object first.")
        if action == "give":
            recipient = next(
                (
                    candidate
                    for candidate in world.get("players", {}).values()
                    if candidate.name.casefold() == str(command.get("target_player")).casefold()
                    and candidate.current_room_id == player.current_room_id
                ),
                None,
            )
            if recipient is not None:
                error = carry_error(item, recipient, world)
                if error:
                    return result("The recipient cannot carry that much weight.")
        return None  # Legacy transfer code owns room/player notifications.
    return result("That object has no supported rule for this action.")
