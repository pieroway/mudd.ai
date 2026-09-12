# Discovered-world map

The Map button opens a visual map beside the transcript. Use `/map show`,
`/map hide`, `/map expand`, or `/map collapse`; `map` and `/panel map` are also
accepted locally. Visibility is saved in this browser. These commands do not
move your character or use AI units.

The map marks your current room with **You are here**. Select a room to read
its known outgoing directions and destinations. Use +/− to zoom, drag the
background or use the arrow buttons to pan, and **Center on me** to reset the
view. Expand provides more space while preserving the transcript and prompt.
The same controls work on narrow screens, where map and inventory have independent
scroll areas below the transcript. The viewport adapts to its available size so
room labels retain their size. Open a room's known-exits disclosure for directions.

Discovery belongs to each character and persists in PostgreSQL across reconnects
and restarts. Connecting discovers the current room; movement records the new
room in the same transaction as player location. Failed movement reveals nothing.
The migration seeds existing characters with only their current room because
historical visits were not recorded. Revisit older locations to add them.

The server sends visited room IDs/names and canonical exits whose two endpoints
are both visited. Unvisited destinations and proposal drafts are excluded, even
for administrators. Normal `look` still shows available directions for exploration.
Other players' discovery records are never used for your map. Narration cannot
change map state, and the panel hides stale geography when disconnected.

This is a schematic connection diagram, not a geographic scale map. Compass
directions guide placement; overlapping nodes are shifted so rooms remain
distinct. Vertical exits appear as diagonal connections with explicit up/down
labels in the selected room's exit list. Separate floors, landmarks, secret-route
visibility rules, player tracking, and click-to-travel remain future work. The
current world has no secret-exit model; a future one must filter server-side
before adding exits to map snapshots.

Implementation uses migration `0013` (`player_discoveries`), authoritative
`ClientState.map` snapshots over the existing authenticated WebSocket, and a
React/SVG panel with no new dependencies. Browser layout state is local; discovery
and topology are server-owned. Snapshots currently include the whole discovered
graph; larger worlds may require a bounded viewport API.

## Validation

September 9, 2026:

- Backend lint, type checking (51 files), and all 336 tests passed, exit 0;
  coverage 93%. Two existing dependency deprecation warnings remain.
- Frontend lint, type checking, all 23 tests, and build passed on the final
  adaptive viewport, exit 0.
- The initial browser run passed 11 workflows and caught a mobile inventory
  visibility regression, exit 1. Independent panel scroll areas fixed it; all 12
  workflows then passed, exit 0. After the adaptive viewport change, 11 workflows
  passed and the map test needed to pan before selecting an offscreen room. That
  corrected map workflow passed separately, exit 0, including full visibility of
  the current-room marker on mobile. Desktop/mobile screenshots were reviewed.
- Production-like configuration and final application image builds passed,
  exit 0, including rebuilt local and production frontends after viewport changes.
- Backup `backups/pre-map/muddb-20260909T224743064Z-57edcfa6.dump` was created and
  restored in isolation, both exit 0: revision `0012`, 8 rooms, 11 players, 2 NPC
  memories. The backup script used a process-only PowerShell execution-policy
  override because the host's default policy blocks scripts.
- Migration downgrade/upgrade succeeded in the isolated test database, exit 0.
  Backfill matched every existing test character's current room with no extra
  discoveries.
- Initial load smoke exceeded the latency threshold (p95 1.74 s) while concurrent
  builds/browser tests were running, exit 1; state invariants passed. The solo
  rerun passed without changing thresholds, exit 0: 10 users for 30 seconds,
  zero failures in 278 measured commands, p95 568.64 ms, state invariants passed.
- Local deployment completed after all checks, exit 0. Revision `0013` is active,
  all 11 existing characters have their current room discovered, and both app
  services are healthy. The normal source mounts are restored and the temporary
  image-only override was removed. No live AI calls were made during verification.
