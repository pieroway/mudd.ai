# UI Milestone — Modern Command-First Client

## Status and Sequence

**In progress — first UI implementation delivered September 6, 2026. The full deployment gate remains pending.**

This is a separate UI milestone following M2, with the first delivery increment
proposed before M3. It does not renumber M3 (AI narration), M4 (one AI NPC), or
M5 (controlled world generation). This document defines delivery scope; the
[UI inspiration brief](docs/mud_ai_ui_inspiration.md) supplies broader visual direction.

## Goal

Make the existing game easier to read and use through a responsive client with
optional context panels. The transcript and command prompt remain the primary
interface and remain usable with every panel hidden.

## Scope

- A readable, responsive layout: top status bar, central transcript, optional
  navigation area, and collapsible context panels.
- Live character name, current room, connection status, and daily AI allowance.
- An inventory panel populated by structured authoritative server state.
- Keyboard-accessible panel controls and local show/hide commands with explicit
  syntax such as `/panel inventory show` and `/panel inventory hide`.
- Saved panel visibility, preserved existing themes, and clear focus behavior.
- Automated coverage of panel behavior, state synchronization, and existing
  terminal workflows.

The first release uses only information the backend supports. Maps, health bars,
equipment, and social navigation from the inspiration brief are future extensions;
mock versions may appear in an isolated prototype, but not as live game state.

## Architectural Boundaries

- The engine owns inventory, location, and all other game facts. Panels display
  server-provided data and never infer state from transcript prose.
- Keep authoritative snapshots separate from local layout preferences. Only
  presentation preferences belong in browser storage.
- Reuse authenticated WebSockets and the existing command execution path.
  Panel commands affect browser layout; classic `inventory` / `i` retain their
  existing gameplay behavior and do not require AI.
- Define typed, validated server payloads and matching frontend types before
  wiring live panels. Send only the authenticated player's authorized data.
- Supply inventory on connection and refresh it after successful inventory
  changes. Reconnect obtains a fresh snapshot; stale data must not appear current.
- Do not add another state framework or transport unless existing React and
  WebSocket patterns prove insufficient.

## Affected Modules

- `frontend/src/components/Terminal.tsx`: retain connection and command behavior
  while extracting focused layout and panel components as needed.
- `frontend/src/components/Transcript.tsx` and `CommandPrompt.tsx`: readable feed,
  keyboard focus, and an always-accessible prompt.
- `frontend/src/styles/`: responsive layout and existing theme integration.
- `backend/app/api/websocket.py`, `backend/app/services/game.py`, and repository
  reads: authorized structured snapshots and refresh delivery where needed.
- `backend/tests/`, frontend tests, and `e2e/tests/`: regression and feature coverage.

Exact component boundaries and message fields should be settled after inspecting
the current implementation. No database migration is expected for layout state;
any newly discovered persistence requirement needs an explicit design.

## Delivery Increments

### 1. Layout and component plan

- [x] Inspect existing transport, transcript, theme, and test behavior.
- [x] Define component responsibilities and the inventory snapshot contract.
- [x] Build the responsive shell around the working transcript and prompt.
- [x] Show existing live status information in the top bar.
- [x] Check desktop and narrow-screen layouts and keyboard navigation.

If an isolated mock prototype helps review, label its data as simulated. Integrate
the existing live client incrementally rather than maintaining a second client.

### 2. Authoritative inventory panel

- [x] Add tests for authorized snapshots, empty inventory, successful take/drop,
  failed actions, and reconnect refresh.
- [x] Implement structured inventory delivery without parsing narrative text.
- [x] Render inventory and explicit empty, disconnected, and stale states.
- [x] Add panel controls and local panel commands; preserve classic commands.
- [x] Persist visibility preferences without storing authoritative inventory.

### 3. Usability and verification

- [x] Preserve theme selection and existing authentication, command, and debug behavior.
- [x] Verify the prompt stays usable with panels open or hidden and on narrow screens.
- [x] Verify keyboard focus, control labels, and readable contrast.
- [x] Run relevant backend and frontend tests using deterministic doubles.
- [x] Add focused Playwright coverage for panel visibility, item changes, and reconnect.
- [ ] Run the complete Docker deployment gate before deployment and record results.
- [x] Update README and UI documentation with supported commands and behavior.

## Definition of Done

- A player can sign in, issue commands, and read the transcript across supported
  desktop and narrow layouts without panels obstructing the prompt.
- Live status and inventory reflect authorized server state; failed actions do
  not fabricate changes, and reconnect restores current inventory.
- Panels work through accessible controls and documented local commands, and
  visibility preferences survive reload.
- Existing gameplay, authentication, themes, and AI allowance behavior are preserved.
- Required lint, type checks, backend/frontend unit tests, Docker builds,
  integration tests, Playwright tests, and the deployment script's additional
  checks pass. Record actual exit codes; stop deployment on any required failure.

## Deferred Extensions

- Discovered-area map: requires a server-owned discovery and visibility contract.
- Nearby-player map tracking: set radius, names when known, and distinct colors
  for known versus not-yet-interacted-with players. Deferred to a later mapping
  phase; see [the roadmap](docs/ROADMAP.md#deferred-map-player-tracking).
- Multi-user communications panel: membership, privacy, and reconnect policy are
  tracked in [docs/ROADMAP.md](docs/ROADMAP.md).
- Health, stats, equipment, quests, and NPC panels as their game systems arrive.
- Resizable panels, channel filtering, autocomplete, notifications, and richer
  saved layouts after the first usable release.
- AI onboarding, suggestions, and summaries as separately scoped work. Existing
  natural-language command interpretation remains available.

## Validation Record


September 6, 2026:

- Frontend baseline: 15 tests, lint, type checking, and build passed (exit 0).
- Updated frontend Docker checks: 17 tests, lint, type checking, and build passed (exit 0).
- Backend Docker suite: 183 tests passed (exit 0); separate Ruff and mypy checks passed (exit 0).
- Playwright: 6 browser workflows passed, including inventory changes, reload,
  saved visibility, keyboard panel controls, and a 390 × 844 viewport check (exit 0).
- Visually reviewed desktop and mobile screenshots; prompt and inventory remain visible.
- The full deployment gate has not been run and this increment is not deployed.

The new optional `state` field on authenticated system/game-output messages contains
`room_id`, `room_name`, and `inventory` entries with only `id` and `name`. A single
SQL query scopes the snapshot to the session's player. Command responses and
multiplayer event recipients receive current snapshots. InventoryPanel renders
these values; Terminal owns transport and local visibility preferences.

Known limits: reconnect currently uses page reload, following the existing client
behavior. Snapshots add one read per command response/event recipient; revisit
selective refresh if profiling shows this matters. The full deployment gate remains a milestone completion requirement.
