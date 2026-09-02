from __future__ import annotations


def parse_command(raw: str):
    """Parse a raw command string into a simple normalized form."""
    text = (raw or "").strip()
    if not text:
        return {"action": "unknown", "raw": text}

    parts = text.lower().split()
    command = parts[0]
    target = " ".join(parts[1:]) if len(parts) > 1 else None

    if command in {"look", "l"} and len(parts) > 1 and parts[1] in {"in", "inside"}:
        return {
            "action": "look_in",
            "container": " ".join(parts[2:]) or None,
            "raw": text,
        }

    if command in {"get", "take"} and "from" in parts[1:]:
        separator = parts.index("from", 1)
        return {
            "action": "take_from",
            "target": " ".join(parts[1:separator]) or None,
            "container": " ".join(parts[separator + 1 :]) or None,
            "raw": text,
        }
    if command == "put":
        put_separator: int | None = None
        for index in range(1, len(parts)):
            if parts[index] in {"in", "into"}:
                put_separator = index
                break
        if put_separator is None:
            return {
                "action": "put",
                "target": target,
                "container": None,
                "raw": text,
            }
        return {
            "action": "put",
            "target": " ".join(parts[1:put_separator]) or None,
            "container": " ".join(parts[put_separator + 1 :]) or None,
            "raw": text,
        }

    if command in {"look", "l"}:
        return {"action": "look", "raw": text}
    if command in {"north", "n"}:
        return {"action": "move", "direction": "north", "raw": text}
    if command in {"south", "s"}:
        return {"action": "move", "direction": "south", "raw": text}
    if command in {"east", "e"}:
        return {"action": "move", "direction": "east", "raw": text}
    if command in {"west", "w"}:
        return {"action": "move", "direction": "west", "raw": text}
    if command in {"inventory", "i"}:
        return {"action": "inventory", "raw": text}
    if command in {"get", "take"}:
        return {"action": "take", "target": target, "raw": text}
    if command == "drop":
        return {"action": "drop", "target": target, "raw": text}
    if command in {"examine", "inspect"}:
        return {"action": "examine", "target": target, "raw": text}
    if command in {"open", "close", "use"}:
        return {"action": command, "target": target, "raw": text}
    if command in {"help"}:
        return {"action": "help", "raw": text}

    return {"action": "unknown", "raw": text, "target": target}
