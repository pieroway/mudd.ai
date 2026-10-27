"""Viewer-safe facts and descriptions shared by commands and client snapshots."""

from app.domain.item import Item


def root(item, items):
    seen = set()
    while item.container_id:
        if item.id in seen or item.container_id not in items:
            return None
        seen.add(item.id)
        item = items[item.container_id]
    return item


def has_light(player, world):
    room = world["rooms"][player.current_room_id]
    if not room.conditions.get("dark", False):
        return True
    for item in world["items"].values():
        origin = root(item, world["items"])
        if origin and item.is_lit and (origin.owned_by == player.id or origin.room_id == room.id):
            # Light inside a closed container does not illuminate the room.
            current = item
            while current.container_id:
                current = world["items"][current.container_id]
                if current.can_open and not current.is_open:
                    break
            else:
                return True
    return False


def visible(item, player, world, *, ignore_hidden=False):
    if item is None:
        return False
    items = world["items"]
    seen = set()
    current = item
    while True:
        if current.id in seen:
            return False
        seen.add(current.id)
        if (
            current.discovery.get("hidden")
            and player.id not in current.discovery.get("discovered_by", [])
            and not ignore_hidden
        ):
            return False
        if current.container_id:
            parent = items.get(current.container_id)
            if parent is None:
                return False
            placement = current.relationships.get("placement", "contained_in")
            if placement == "contained_in" and parent.can_open and not parent.is_open:
                return False
            if parent.state.get("locked") and placement == "contained_in":
                return False
            current = parent
        else:
            if current.owned_by == player.id:
                return True
            return current.room_id == player.current_room_id and has_light(player, world)


def accessible(item, player, world):
    return visible(item, player, world)


def find_item(target, player, world, *, owned=False, room_only=False):
    if not target:
        return None
    target = target.casefold().strip()
    matches = []
    for item in world["items"].values():
        if target not in {
            item.id.casefold(),
            item.name.casefold(),
            *(alias.casefold() for alias in item.aliases),
        }:
            continue
        if not visible(item, player, world):
            continue
        if owned and item.owned_by != player.id:
            continue
        if room_only and item.room_id != player.current_room_id:
            continue
        matches.append(item)
    # Never let an ambiguous alias select an arbitrary lock, key, or object.
    identifiers = [item for item in matches if item.id.casefold() == target]
    if identifiers:
        return identifiers[0]
    exact = [item for item in matches if target == item.name.casefold()]
    selected = exact or matches
    return selected[0] if len(selected) == 1 else None


def total_weight(item, items, seen=None):
    seen = set() if seen is None else seen
    if item.id in seen:
        raise ValueError("Containment cycle")
    seen.add(item.id)
    return ((item.weight_kg or 0) + item.state.get("liquid_litres", 0)) * item.quantity + sum(
        total_weight(child, items, seen.copy())
        for child in items.values()
        if child.container_id == item.id
    )


def volume(item):
    dimensions = item.dimensions_cm
    if all(dimensions.get(key) for key in ("length", "width", "height")):
        return (
            dimensions["length"] * dimensions["width"] * dimensions["height"] / 1000 * item.quantity
        )
    return {"tiny": 0.01, "small": 0.5, "medium": 5, "large": 80, "huge": 1000}.get(
        item.size, 0
    ) * item.quantity


def state_words(item):
    words = []
    if item.can_open:
        words.append("open" if item.is_open else "closed")
    for key, adjective in [
        ("locked", "locked"),
        ("wet", "wet"),
        ("broken", "broken"),
        ("folded", "folded"),
        ("active", "active"),
    ]:
        if item.state.get(key) or (key == "broken" and item.condition.get("broken")):
            words.append(adjective)
    if item.is_light_source:
        words.append("lit" if item.is_lit else "unlit")
    if (
        item.durability is not None
        and item.maximum_durability
        and 0 < item.durability < item.maximum_durability
    ):
        words.append("damaged")
    if item.state.get("tied"):
        words.append("tied")
    if item.state.get("shifted"):
        words.append("shifted aside")
    if item.state.get("afloat"):
        words.append("afloat")
    if item.state.get("leaking"):
        words.append("leaking")
    if "fillable" in item.capabilities:
        words.append("empty" if not item.state.get("liquid_litres") else "contains liquid")
    return words


def describe(item: Item, player, world, context="examine"):
    name = f"{item.quantity} {item.name}" if item.quantity > 1 else item.name
    slot = item.relationships.get("slot")
    equipment = item.relationships.get("equipment")
    if context == "examine":
        text = item.description
    elif item.owned_by == player.id:
        if slot in {"left_hand", "right_hand", "both_hands"}:
            verb = "wield" if equipment == "wielded" else "hold"
            text = f'You {verb} the {name} in your {slot.replace("_", " ")}.'
        elif equipment == "worn":
            text = f"You wear the {name} on your {slot}."
        else:
            text = f"You carry the {name}."
    elif item.container_id:
        parent = world["items"].get(item.container_id)
        placement = item.relationships.get("placement", "contained_in")
        preposition = {
            "resting_on": "on",
            "hidden_under": "beneath",
            "attached_to": "attached to",
        }.get(placement, "inside")
        text = f'The {name} rests {preposition} the {parent.name if parent else "object"}.'
    elif item.owned_by:
        owner = world.get("players", {}).get(item.owned_by)
        text = f'{owner.name if owner else "Someone"} carries the {name}.'
    else:
        text = f"The {name} is here."
    words = state_words(item)
    if words:
        text += " It is " + ", ".join(words) + "."
    if context == "examine" and item.discovery.get("clue"):
        text += " " + str(item.discovery["clue"])
    return text


def suggested_actions(item):
    actions = ["examine"]
    mapping = {
        "takeable": "take",
        "holdable": "hold",
        "wearable": "wear",
        "wieldable": "wield",
        "readable": "read",
        "searchable": "search",
        "container": "look in",
        "surface": "look on",
        "movable": "push",
        "sittable": "sit",
        "lieable": "lie down",
        "enterable": "board",
        "lightable": "light",
        "extinguishable": "extinguish",
        "climbable": "climb",
        "consumable": "use",
        "lockable": "unlock" if item.state.get("locked") else "lock",
    }
    actions.extend(action for cap, action in mapping.items() if cap in item.capabilities)
    if item.can_open:
        actions.append("close" if item.is_open else "open")
    if item.owned_by:
        actions.append("drop")
    return actions
