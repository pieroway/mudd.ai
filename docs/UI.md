# UI

The [UI milestone plan](../MILESTONE_UI_PLAN.md) tracks the first release,
delivery checklist, architectural boundaries, and validation requirements. The
[inspiration brief](mud_ai_ui_inspiration.md) describes the broader visual direction.

Primary interface remains command-first: transcript/output plus prompt input.

The first implementation has a responsive transcript and inventory layout with
live character name, room, connection status, and daily AI allowance. On narrow
screens, inventory sits below the transcript while the prompt remains accessible.

Use the **Inventory** button or `/panel inventory show` and `/panel inventory hide`.
Visibility is saved locally. Classic `inventory` / `i` still go to the game engine.
The panel updates after commands and multiplayer events, including received items.
On disconnect it hides stale contents; reload to reconnect and obtain fresh state.
Existing `/theme light | dark | techo`, `/debug on | off`, and command history remain.

Future panels may include map, equipment, health, stats, quests, nearby players/NPCs,
and combat status. These require their corresponding authoritative game systems.

Frontend consumes structured server state instead of parsing narration text.

Keep authoritative game state separate from browser layout state.

Map support may later include current location, discovered rooms, zoom, pan, scrolling, multiple floors, regions, and landmarks.

Never send secret/undiscovered map data merely to hide it client-side.

Later mapping should consider tracking nearby players within a set radius,
showing names when known, and using distinct colors for known players versus
players the viewer has not interacted with. See the
[deferred map player tracking requirements](ROADMAP.md#deferred-map-player-tracking)
for scope and open decisions. This is deferred beyond the current UI increment.
