# Roadmap

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

## Later Gameplay
Design for, defer:
- authenticated administrator roles and admin-only debug diagnostics
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
