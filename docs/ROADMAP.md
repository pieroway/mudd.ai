# Roadmap

## UI Milestone — Complete

See [MILESTONE_UI_PLAN.md](../MILESTONE_UI_PLAN.md) for the modern command-first
client milestone. Its first increment was delivered after M2 and before M3, without
renumbering the AI milestones. Initial scope is a responsive shell, live status,
and an authoritative inventory panel. Maps and multi-user chat remain extensions
with separate backend requirements. The first implementation and full deployment
gate passed September 6, 2026, and the local development stack is deployed.
Optional AI narration (M3) passed its full deployment gate September 6, 2026;
see [the M3 plan](../MILESTONE_THREE_PLAN.md). The [M4 NPC](../MILESTONE_FOUR_PLAN.md)
is deployed locally and confirmed working by the owner September 8, 2026: Edric at the Inn, with private
conversations, bounded knowledge, and persistent per-character memory.
Controlled AI world generation is implemented; see the [M5 implementation plan](../MILESTONE_FIVE_PLAN.md).
The first increment is one admin-reviewed room with reciprocal exits and atmospheric
descriptions of up to five sentences. Required checks passed and the first increment
is deployed locally, including admin description editing and persistent relative movement.
See [world generation commands](WORLD_GENERATION.md) for operator usage.
Local nightly backups are available; a second copy is deferred until non-local
storage is available. See [backup and recovery](BACKUPS.md).

The project owner confirmed `/ai narration on|off` is working September 7, 2026.
Making narration sound more like a poet is deferred for a later refinement pass.

## Core Architecture
Build early:
- Docker / Compose / Docker Desktop
- FastAPI / WebSockets
- PostgreSQL / migrations
- command parser and router
- authoritative game engine
- shared rooms and items
- multiplayer presence
- pytest
- Playwright
- deployment quality gate
- AI provider abstraction
- FakeAIProvider

## Early Gameplay

The next M5 increment implements [reviewed neighborhoods](NEIGHBORHOODS.md):
bounded connected rooms, buildings, shared doors, fixtures, and containers through
`/world generate`, with full text review and atomic approval. It passed all required
checks and was deployed locally September 11, 2026; results are recorded there.

After core is stable:
- natural-language commands
- player item transfer
- multi-user private communications panel (deferred from Milestone One)
- in-game currency
- one merchant/stall
- direct player trading
- first AI NPC
- optional AI narration
- one manually designed empowered artifact
- basic optional UI panels
- basic discovered-area map

### Discovered-World Map

The first [map increment](MAP.md) implements per-character room discovery,
known connections, current position, zoom/pan, and expand/collapse controls.
The required checks passed and it is deployed locally; validation is recorded
in the map documentation. Nearby-player tracking
remains separate, as selected by the owner September 9, 2026.

### Deferred Map Player Tracking

Requested September 6, 2026 for consideration in a later mapping phase, outside
the current UI increment:

- Track other players within a set radius of the viewing player.
- Display names when the viewing player knows them; otherwise use an unnamed marker.
- Color-code known players separately from players the viewer has not interacted
  with. Include a label or marker shape so color is not the only distinction.
- Have the server determine range, visibility, and what the viewer knows. Send
  only authorized nearby-player data, respecting map discovery and hidden areas.

Decide during mapping design: the radius and distance metric (for example, room
hops), what interaction establishes familiarity or reveals a name, whether that
knowledge persists, and how markers update when players move or disconnect.
These are open design decisions, not behavior implemented by the current UI.

### Deferred Multi-User Communications Panel

Add a side panel opened with `/chat Alan Kim` (with `/open chat with Alan, Kim`
as an optional friendly alias). This is intentionally post-Milestone-One because
it requires conversation membership, authorization, privacy, reconnect behavior,
and abuse controls in addition to frontend layout.

Implement it incrementally:

1. Reuse authenticated WebSocket connections and structured events; never derive
   chat state by parsing transcript text.
2. Have the server create or resolve a conversation and authorize every member
   and message recipient.
3. Start with connected users and ephemeral conversations, then add persistence,
   unread state, invitations, offline delivery, blocking, moderation, and rate
   limits only when their policies are defined.
4. Keep panel visibility, size, and focus as local UI state while conversation
   membership and message routing remain server-owned.

Open design decisions include invitation consent, who may add members, history
retention, offline participation, membership changes, and blocking behavior.

### Deferred Engine-Owned Destination Navigation

Support natural requests such as `walk toward the docks` with a structured
destination intent rather than asking an AI provider to invent directions:

```json
{"action": "navigate", "destination": "docks"}
```

The AI layer may identify the requested destination, but the authoritative game
engine must determine the player's current location, whether the destination is
known and reachable, and which exits form a valid route. The engine should then
execute one step at a time or expose a cancellable travel policy; it must never
accept provider-supplied geography as fact.

Before implementation, decide how destination ambiguity, player map knowledge,
locked or changing routes, interruption, hazards, and multiplayer movement
events affect navigation. The current `walk toward the docks` fake fixture is
only a narrow interpretation-pipeline example and not general pathfinding.

## Later Gameplay
Design for, defer:
- admin-only debug diagnostics (account roles and admin-only `/ai` are implemented)
- progression
- equipment
- crafting
- factions
- housing
- guilds
- PvP
- death
- crime
- world events
- environmental simulation
- parties
- auctions
- mail
- moderation
- world builder
- admin tools

## Experimental AI
Much later:
- generated world expansion
- generated artifacts
- emergent quests
- AI Dungeon Master layer
- NPC-to-NPC simulation
- rumour propagation
- living history generation
- personalized narration

Architect now does not mean implement now.
