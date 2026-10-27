"""Unambiguous item grammar; interpretation never performs an action."""

import re


def parse_item_command(text):
    text = " ".join(text.casefold().split())
    match = re.fullmatch(r"(tie|attach) (.+?) to (.+?) with (.+)", text)
    if match:
        return {
            "action": match[1],
            "target": match[2],
            "destination": match[3],
            "tool": match[4],
            "raw": text,
        }
    match = re.fullmatch(r"pilot (.+?) (north|south|east|west|n|s|e|w)", text)
    if match:
        from app.domain.directions import DIRECTIONS

        return {
            "action": "pilot",
            "target": match[1],
            "direction": DIRECTIONS[match[2]],
            "raw": text,
        }
    match = re.fullmatch(r"(give|spend) (\d+) (.+?) to (.+)", text)
    if match:
        return {
            "action": match[1],
            "quantity": int(match[2]),
            "target": match[3],
            "target_player": match[4],
            "raw": text,
        }
    for pattern, action in [
        (r"pick up (.+)", "take"),
        (r"look at (.+)", "examine"),
        (r"look (?:under|beneath|behind) (.+)", "look_under"),
        (r"lie down (?:on )?(.+)", "lie"),
        (r"enter (.+)", "board"),
        (r"move (.+)", "move_object"),
        (r"lift (.+)", "move_object"),
        (r"pick (.+?) lock", "pick_lock"),
    ]:
        match = re.fullmatch(pattern, text)
        if match:
            return {"action": action, "target": match[1], "raw": text}
    match = re.fullmatch(r"(?:look on|look atop) (.+)", text)
    if match:
        return {"action": "look_on", "container": match[1], "raw": text}
    match = re.fullmatch(r"put (.+?) (on|onto) (.+)", text)
    if match:
        return {
            "action": "put",
            "target": match[1],
            "container": match[3],
            "placement": "resting_on",
            "raw": text,
        }
    match = re.fullmatch(r"(hold|wield) (.+?) (?:in|with) (?:my |the )?(left|right) hand", text)
    if match:
        return {"action": match[1], "target": match[2], "slot": match[3] + "_hand", "raw": text}
    match = re.fullmatch(r"(attach|tie) (.+?) to (.+)", text)
    if match:
        return {"action": match[1], "target": match[2], "destination": match[3], "raw": text}
    match = re.fullmatch(r"(pour|fill|combine) (.+?) (?:into|in|from|with) (.+)", text)
    if match:
        return {"action": match[1], "target": match[2], "destination": match[3], "raw": text}
    match = re.fullmatch(r"(split|spend) (\d+) (.+)", text)
    if match:
        return {"action": match[1], "quantity": int(match[2]), "target": match[3], "raw": text}
    match = re.fullmatch(
        r"(lock|unlock|break|repair|light|read|pry|pick|dig|harvest|cut|slash|stab) (?:up )?(.+?) with (.+)",
        text,
    )
    if match:
        action = "pick_lock" if match[1] == "pick" else match[1]
        return {
            "action": action,
            "target": match[2].removesuffix(" lock"),
            "tool": match[3],
            "raw": text,
        }
    match = re.fullmatch(r"read (front|back|folds|seal|cover|pages|margins) of (.+)", text)
    if match:
        return {"action": "read", "target": match[2], "part": match[1], "raw": text}
    action, _, target = text.partition(" ")
    if action in {
        "hold",
        "release",
        "wear",
        "wield",
        "remove",
        "search",
        "lock",
        "unlock",
        "read",
        "push",
        "pull",
        "break",
        "repair",
        "light",
        "attach",
        "detach",
        "tie",
        "untie",
        "climb",
        "sit",
        "board",
        "leave",
        "pour",
        "fill",
        "fold",
        "unfold",
        "switch",
        "dig",
        "harvest",
        "throw",
        "pry",
        "consume",
        "eat",
        "drink",
        "launch",
        "beach",
    }:
        return {
            "action": "consume" if action in {"eat", "drink"} else action,
            "target": target.removeprefix("on ") or ("room" if action == "search" else None),
            "raw": text,
        }
    return None
