from __future__ import annotations


def parse_command(raw: str):
    """Parse a raw command string into a simple normalized form."""
    text = (raw or "").strip()
    if not text:
        return {"action": "unknown", "raw": text}

    parts = text.lower().split()
    command = parts[0]
    target = " ".join(parts[1:]) if len(parts) > 1 else None

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
    if command in {"help"}:
        return {"action": "help", "raw": text}

    return {"action": "unknown", "raw": text, "target": target}
