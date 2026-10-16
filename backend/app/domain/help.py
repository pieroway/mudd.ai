from __future__ import annotations

from collections.abc import Iterable
from typing import TypedDict


class HelpEntry(TypedDict):
    command: str
    description: str


class HelpGroup(TypedDict):
    title: str
    entries: list[HelpEntry]


_BASE_HELP: tuple[tuple[str, tuple[tuple[str, str], ...]], ...] = (
    (
        "MOVEMENT",
        (
            ("north / n", "Move north."),
            ("south / s", "Move south."),
            ("east / e", "Move east."),
            ("west / w", "Move west."),
            ("up / u", "Move up one level."),
            ("down / d", "Move down one level."),
            (
                "forward",
                "Move forward relative to your facing direction.",
            ),
            (
                "backward / backwards",
                "Move backward relative to your facing direction.",
            ),
            ("left / right", "Turn and move relative to your facing direction."),
        ),
    ),
    (
        "LOOKING AND STATUS",
        (
            ("look / l", "Describe your location, exits, and visible objects."),
            ("examine / inspect <target>", "Examine an object or door."),
            ("look in <container>", "View the contents of an open container."),
            ("inventory / i", "List what you are carrying."),
            ("who [page]", "List connected players."),
        ),
    ),
    (
        "ITEMS",
        (
            ("take / get <item>", "Pick up a portable item."),
            (
                "take / get <item> from <container>",
                "Retrieve an item from an open container.",
            ),
            ("drop <item>", "Place a carried item in the room."),
            (
                "give <item> to <player>",
                "Give an item to a player in the same room.",
            ),
            (
                "put <item> in <container>",
                "Store a carried item in an open container.",
            ),
            ("open / close <target>", "Open or close a door or container."),
            ("use <item>", "Use a carried item."),
            ("use <tool> on <target>", "Use a carried tool on a world object."),
            (
                "extinguish / douse <item>",
                "Extinguish a carried light source.",
            ),
        ),
    ),
    (
        "OBJECT INTERACTIONS",
        tuple(
            (
                f"{verb} <target> with <tool>",
                f"{description} a supported target.",
            )
            for verb, description in (
                ("wipe", "Clean"),
                ("unlock", "Unlock"),
                ("repair", "Repair"),
                ("light", "Light"),
                ("read", "Read"),
                ("reveal", "Reveal something on"),
            )
        ),
    ),
    (
        "COMMUNICATION",
        (
            ("say <message>", "Speak to everyone in the room."),
            (
                "say to <player> <message>",
                "Speak privately to a player.",
            ),
            ("tell <player> <message>", "Speak privately to a player."),
            ("talk <npc> <message>", "Have a private conversation with an NPC."),
        ),
    ),
    (
        "INTERFACE",
        (
            ("/map show / hide", "Show or hide the map."),
            ("/map expand / collapse", "Change the map size."),
            (
                "/panel inventory show / hide",
                "Show or hide the inventory panel.",
            ),
            ("/theme light / dark / techno", "Change the interface theme."),
            ("/debug on / off", "Show or hide connection diagnostics."),
            ("help", "Display this command reference."),
        ),
    ),
)

_ADMIN_HELP: tuple[tuple[str, tuple[tuple[str, str], ...]], ...] = (
    (
        "AI ADMINISTRATION",
        (
            (
                "/ai narration on / off",
                "Enable or disable narration for your account.",
            ),
            (
                "/ai credits add <username> [units]",
                "Grant AI credits; defaults to 50 units.",
            ),
        ),
    ),
    (
        "WORLD BUILDING",
        (
            ("/world generate [options]", "Propose a neighborhood."),
            (
                "/world propose <direction> <brief>",
                "Propose one connected room.",
            ),
            ("/world proposals", "List your recent proposals."),
            ("/world preview <id>", "Review a proposal."),
            ("/world approve <id>", "Publish a proposal."),
            ("/world reject <id>", "Reject a proposal."),
            ("/world rename <name>", "Rename the current room."),
            (
                "/world describe <description>",
                "Replace the current room description.",
            ),
            (
                '/world interaction <verb> "<tool>" "<target>"',
                "Create a configured object interaction.",
            ),
            ("/world delete <direction>", "Preview deletion of a world branch."),
            (
                "/world confirm-delete <token>",
                "Confirm a previously previewed deletion.",
            ),
        ),
    ),
)


def _groups(
    definitions: Iterable[tuple[str, tuple[tuple[str, str], ...]]],
) -> list[HelpGroup]:
    return [
        {
            "title": title,
            "entries": [
                {"command": command, "description": description}
                for command, description in entries
            ],
        }
        for title, entries in definitions
    ]


def player_help_groups() -> list[HelpGroup]:
    return _groups(_BASE_HELP)


def admin_help_groups() -> list[HelpGroup]:
    return _groups(_ADMIN_HELP)


def format_help(groups: Iterable[HelpGroup]) -> str:
    lines = ["Available commands", ""]
    for group in groups:
        lines.append(group["title"])
        lines.extend(
            f'{entry["command"]} — {entry["description"]}'
            for entry in group["entries"]
        )
        lines.append("")
    return "\n".join(lines)
