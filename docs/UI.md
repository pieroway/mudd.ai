# UI

Primary interface remains command-first: transcript/output plus prompt input.

Future optional panels may include map, inventory, equipment, health, stamina, mana, stats, skills, quests, journal, nearby players/NPCs, and combat status.

Commands may show/hide panels.

Frontend consumes structured server state instead of parsing narration text.

Keep authoritative game state separate from browser layout state.

Map support may later include current location, discovered rooms, zoom, pan, scrolling, multiple floors, regions, and landmarks.

Never send secret/undiscovered map data merely to hide it client-side.
