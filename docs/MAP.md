# Discovered-world map

The Map button opens a visual map beside the transcript. Use `/map show`,
`/map hide`, `/map expand`, or `/map collapse`; `map` and `/panel map` are also
accepted locally. Visibility is saved in this browser. These commands do not
move your character or use AI units.

The map marks your current room with **You are here**. Select a room to read
its known outgoing directions and destinations. Use +/− to zoom, drag the
background or use the arrow buttons to pan, and **Center on me** to reset the
view. **Fit map** frames every displayed floor and continues
to fit when the panel resizes or nearby levels are toggled. Zooming or panning
returns to manual control. Expand provides more space while preserving the
transcript and prompt.
The same controls work on narrow screens, where map and inventory have independent
scroll areas below the transcript. The viewport adapts to its available size so
room labels retain their size. Open a room's known-exits disclosure for directions.

The current level shows the horizontal neighborhood connected to your current
room. **Nearby levels** adds visited neighborhoods up to two floors above and
below it, and saves that toggle in this browser. All room boxes have the same
size. Each floor above is offset to the top-left by 1/8 room width and 1/4 room
height; each floor below is offset to the bottom-right by the same amounts.
Adjacent floors use 38% opacity and floors two steps away use 24%. Distant
floors are drawn first, adjacent floors next, and the current floor last so it
stays on top. Ghost names occupy the exposed top or bottom strip of each box.
Each horizontal component is anchored to its connecting stair room; conflicting
components on the same floor shift sideways to keep their rooms distinct.
Ghost layers never resize or reposition the current neighborhood. Moving vertically makes
the destination neighborhood the new current level. Floor relationships are
inferred from up/down exits, since rooms do not store absolute floor numbers.
Only consecutive upward or downward connections extend the preview; detours
through another floor do not pull in disconnected neighborhoods on this floor.

Room-corner **↑ / ↓** badges indicate available vertical exits, even before the
destination is visited. Up badges sit at the top-right and down badges at the
bottom-right. They reveal no destination identity or geography.
Taller room boxes allow two-line names; labels retain their screen font size on
zoom. At crowded zoom levels, secondary labels disappear before becoming tiny.
Hover or focus a room for its full name, or select it to see the full name and
known exits below the map. Ghost rooms can be inspected but not used to travel.

On mobile (640 px wide or less), the map shows only the current level and hides
the nearby-levels toggle. Returning to desktop restores the saved preference.
At overview zoom, labels and badges give way to room outlines; zoom in or select
a room to inspect its full name and known exits.

Discovery belongs to each character and persists in PostgreSQL across reconnects
and restarts. Connecting discovers the current room; movement records the new
room in the same transaction as player location. Failed movement reveals nothing.
The migration seeds existing characters with only their current room because
historical visits were not recorded. Revisit older locations to add them.

The server sends visited room IDs/names and canonical exits whose two endpoints
are both visited, plus `has_up`/`has_down` flags for each visited room.
Unvisited destinations and proposal drafts are excluded, even
for administrators. Normal `look` still shows available directions for exploration.
Other players' discovery records are never used for your map. Narration cannot
change map state, and the panel hides stale geography when disconnected.

This is a schematic connection diagram, not a geographic scale map. Compass
directions guide placement; overlapping nodes are shifted so rooms remain
distinct. Vertical relationships use the overlapping floor previews, corner
badges, and explicit directions in the selected room's exit list.
Landmarks, secret-route
visibility rules, player tracking, and click-to-travel remain future work. The
current world has no secret-exit model; a future one must filter server-side
before adding exits to map snapshots.

Implementation uses migration `0013` (`player_discoveries`), authoritative
`ClientState.map` snapshots over the existing authenticated WebSocket, and a
React/SVG panel with no new dependencies. Browser layout state is local; discovery
and topology are server-owned. Snapshots currently include the whole discovered
graph; larger worlds may require a bounded viewport API.

## Validation

September 17, 2026 — overlapping floor preview implementation:

- Equal-size floor boxes use 1/8-width horizontal and 1/4-height vertical
  offsets, with current-floor rooms painted on top and labels in ghost strips.
- All 419 backend tests and 36 frontend tests passed; lint, type checks,
  frontend build, production configuration validation, and image builds passed.
- The initial deployment gate stopped at a browser assertion that included the
  current-room highlight stroke in its size comparison. The test now measures
  SVG rectangle geometry independently of stroke width. All 14 browser workflows
  passed on rerun, including exposed-label clicks, floor ordering, offsets,
  bottom-right down badges, and mobile current-level-only behavior.
  Desktop and mobile screenshots were reviewed.
- Remaining deployment stages were resumed sequentially after browser success:
  smoke load passed with zero failures in 280 measured commands, p95 455.2 ms,
  and passing authoritative-state invariants. Local `docker compose up -d --wait`
  passed, exit 0; all four services are healthy, backend health is `ok`, and the
  frontend returns HTTP 200. No database migration or real AI calls were needed.


September 16, 2026 — map readability and mobile current-level view:

- Backend lint, type checking (54 files), and all 419 unit/integration tests
  passed, exit 0; coverage 87%, with two existing dependency warnings.
- Final frontend lint, type checking, all 34 tests, and build passed, exit 0.
  Coverage includes two-line names, obstacle-free stair paths, fitting all floors,
  and switching from fitted to manual controls. An existing auth-test cleanup
  callback was corrected to return void so TypeScript validation could run.
- Production-like configuration and image builds passed, exit 0.
- All 14 browser workflows passed on the final frontend, exit 0, including
  desktop/mobile fit bounds, current-level-only mobile display, and restoration
  of the desktop nearby-floor preference after resizing. Screenshots were reviewed.
  The earlier browser run also passed, but preceded the mobile-only change.
- A read-only snapshot of the owner's discovered map was replayed in a browser
  to inspect the original screenshot's layout. No character movement or live AI
  requests were needed for that review.
- The first load check stopped deployment at p95 1.3 s while other validation
  work overlapped; its authoritative-state invariants passed. The isolated rerun
  passed, exit 0: 10 users for 30 seconds, zero failures in 267 measured commands,
  p95 957.5 ms, and passing state invariants. Thresholds were unchanged.
- Local `docker compose up -d --wait` passed, exit 0, after those checks. All four
  services are healthy; the backend returns `ok` and the frontend returns HTTP 200.
  This change requires no database migration. Changes remain uncommitted.

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
