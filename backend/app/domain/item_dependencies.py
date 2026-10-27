"""Deterministic lock/key solvability and bounded key placement."""

from uuid import uuid4

from app.domain.catalogue import CATALOGUE
from app.domain.item import Item
from app.domain.item_context import root


def room_distances(rooms, origin, maximum=None):
    distances = {origin: 0}
    queue = [origin]
    for key in queue:
        if maximum is not None and distances[key] >= maximum:
            continue
        for neighbor in rooms[key].exits.values():
            if neighbor not in distances and neighbor in rooms:
                distances[neighbor] = distances[key] + 1
                queue.append(neighbor)
    return distances


def validate_dependencies(items, rooms, origin, player_id=None, *, holder_rooms=None):
    reachable = room_distances(rooms, origin)
    holder_rooms = holder_rooms or {}
    locks = [
        item
        for item in items.values()
        if item.state.get("locked")
        and root(item, items)
        and (
            root(item, items).room_id in reachable
            or root(item, items).owned_by == player_id
            and player_id is not None
            or holder_rooms.get(root(item, items).owned_by) in reachable
        )
    ]
    ids = [item.relationships.get("lock_id") for item in locks]
    if any(not lock_id for lock_id in ids) or len(set(ids)) != len(ids):
        raise ValueError("Locked objects require distinct stable locks.")
    available = set()
    opened = set()
    changed = True
    while changed:
        changed = False
        for item in items.values():
            if item.id in available:
                continue
            if item.container_id:
                parent = items.get(item.container_id)
                if parent is None or parent.id not in available:
                    continue
                placement = item.relationships.get("placement", "contained_in")
                if (
                    placement == "contained_in"
                    and parent.state.get("locked")
                    and parent.id not in opened
                ):
                    continue
                if item.discovery.get("hidden") and not (
                    parent.has_capability("searchable")
                    or parent.has_capability("movable")
                    or parent.has_capability("pryable")
                ):
                    continue
            elif (
                item.room_id not in reachable
                and (player_id is None or item.owned_by != player_id)
                and holder_rooms.get(item.owned_by) not in reachable
            ):
                continue
            if item.discovery.get("hidden") and item.room_id and not item.discovery.get("clue"):
                # Search room reveals authored ground hiding places, but generators must provide a clue.
                if item.provenance.get("source") in {"procedural", "ai_generated"}:
                    continue
            available.add(item.id)
            changed = True
        for locked in locks:
            if locked.id not in available or locked.id in opened:
                continue
            lock_id = locked.relationships["lock_id"]
            matching = any(
                key.id in available
                and lock_id in key.relationships.get("opens", [])
                and not key.state.get("broken")
                and not key.condition.get("broken")
                for key in items.values()
            )
            alternatives = locked.relationships.get("alternative_access", [])
            if (
                not matching
                and "pick_lock" in alternatives
                and locked.capabilities.get("lockable", {}).get("pickable")
            ):
                matching = any(
                    tool.id in available
                    and "pick_lock" in tool.capabilities.get("usable", {}).get("actions", [])
                    and not tool.state.get("broken")
                    and 5 + tool.capabilities["usable"].get("skill_bonus", 0)
                    >= locked.capabilities["lockable"].get("difficulty", 10)
                    for tool in items.values()
                )
            if not matching and "break" in alternatives:
                hardness = locked.capabilities.get("breakable", {}).get("hardness")
                matching = hardness is not None and any(
                    tool.id in available
                    and "break" in tool.capabilities.get("usable", {}).get("actions", [])
                    and tool.capabilities["usable"].get("power", 0) >= hardness
                    and not tool.state.get("broken")
                    for tool in items.values()
                )
            if matching:
                opened.add(locked.id)
                changed = True
    if any(locked.id not in opened for locked in locks):
        raise ValueError(
            "Lock/key dependencies are unreachable or cyclic; keep a reachable matching key or explicit alternative."
        )
    for item in items.values():
        if root(item, items) is None:
            raise ValueError("Item locations contain an orphan or cycle.")
    return {"solvable": True, "locks": len(locks), "reachable_objects": len(available)}


def validate_world_dependencies(items, rooms, holder_rooms=None):
    """World integrity is distinct from one actor's permission to use another's key."""
    holder_rooms = holder_rooms or {}
    locks = [item for item in items.values() if item.state.get("locked")]
    lock_ids = [item.relationships.get("lock_id") for item in locks]
    if any(not key for key in lock_ids) or len(lock_ids) != len(set(lock_ids)):
        raise ValueError("Locked objects require distinct stable locks.")
    for item in items.values():
        if root(item, items) is None:
            raise ValueError("Item locations contain an orphan or cycle.")
    origins = set()
    for item in locks:
        physical = root(item, items)
        origin = physical.room_id or holder_rooms.get(physical.owned_by)
        if origin not in rooms:
            raise ValueError("A locked object must have a reachable physical location.")
        origins.add(origin)
    for origin in origins:
        validate_dependencies(items, rooms, origin, holder_rooms=holder_rooms)
    return {"solvable": True, "locks": len(locks), "regions_checked": len(origins)}


def provision_lock(
    item,
    items,
    rooms,
    origin,
    *,
    key_room=None,
    hiding_place=None,
    source="procedural",
    holder_rooms=None,
):
    if not item.has_capability("lockable"):
        raise ValueError("This template does not support locks.")
    lock_id = item.relationships.get("lock_id") or str(uuid4())
    destination = key_room or origin
    if destination not in room_distances(rooms, origin, 3):
        raise ValueError("A required key must be within three reachable rooms.")
    matching = next(
        (
            key
            for key in items.values()
            if lock_id in key.relationships.get("opens", []) and not key.state.get("broken")
        ),
        None,
    )
    if matching is None:
        nearby = room_distances(rooms, origin, 3)
        matching = next(
            (
                key
                for key in items.values()
                if key.template_id == "key_brass_ornate"
                and root(key, items) is not None
                and root(key, items).room_id in nearby
                and not key.state.get("broken")
                and not key.discovery.get("hidden")
                and not key.container_id
            ),
            None,
        )
        if matching:
            matching.relationships.setdefault("opens", []).append(lock_id)
    if matching is None:
        matching = Item.from_template(
            str(uuid4()),
            CATALOGUE["key_brass_ornate"],
            room_id=destination,
            provenance={"source": source, "generation_reason": f"required_key_for_{lock_id}"},
        )
        matching.name = f"{item.name} key"[:100]
        matching.relationships["opens"] = [lock_id]
        items[matching.id] = matching
    item.relationships["lock_id"] = lock_id
    item.state["locked"] = True
    item.is_open = False
    item.state["open"] = False
    if hiding_place:
        parent = items.get(hiding_place)
        parent_root = root(parent, items) if parent else None
        if parent_root is None or parent_root.room_id not in room_distances(rooms, origin, 3):
            raise ValueError("The hiding place must be nearby and reachable.")
        if not (parent.has_capability("searchable") or parent.has_capability("movable")):
            raise ValueError("The hiding place must support discovery.")
        matching.put_in(parent.id)
        matching.relationships["placement"] = "hidden_under"
        matching.discovery = {"hidden": True, "discovered_by": []}
        parent.discovery["clue"] = "Scuff marks suggest something has been concealed beneath it."
    validate_world_dependencies(items, rooms, holder_rooms)
    return matching
