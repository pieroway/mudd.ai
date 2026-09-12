# Reviewed neighborhood generation

An admin can generate a small connected neighborhood, review it in the transcript,
then publish it atomically. Use an unused outdoor direction, or let `around` find
a nearby outdoor frontier:

```text
/world generate around --radius 2 --rooms 8 --buildings 2 --theme "A quiet district of cedar workshops"
/world proposals
/world preview <proposal-id>
/world approve <proposal-id>
/world reject <proposal-id>
```

`/world generate` defaults to `around`, radius 2, at most 8 rooms and 2 buildings.
`--radius` accepts 0–2 outdoor room hops and controls the search for an attachment,
not the size or geographic radius of the generated neighborhood. Explicit compass
directions, n/e/s/w, and relative directions choose an unused exit in the current
outdoor room. Generation never moves the player. Indoor origins can use `around`
to search through a directly connected outdoor room. Existing Inn and Blacksmith
rooms are classified as buildings without changing their existing exits.

`--rooms` accepts 1–12 and `--buildings` accepts 0–4. These are ceilings; a draft
may contain fewer rooms or buildings. Each building has 1–3 internally connected
rooms. The draft has exactly one attachment to the existing world. Connections
are reciprocal and cannot reuse a direction. All rooms must be reachable from
the attachment; every building boundary has a door.

Preview displays all room descriptions, buildings, both directions of every
connection, doors, and objects with their locations. Rooms have 1–3 sentences
(up to 1,000 characters); doors and objects have one sentence (up to 240 characters).
There are at most 24 objects, with at most four distinctly named objects per room,
including contained objects. The existing single-room `/world propose` and
`/world describe` commands retain their five-sentence limits.

Doors begin closed and share one persistent state from both sides. Use
`open north door`, `close south door`, or `examine cedar door`. When multiple doors
match `door`, specify a direction. Opening and closing notify players on both sides.
Closed doors block movement and failed movement reveals no new map room.

Fixtures and containers stay in place. Containers start closed; use `open wooden box`,
`look in wooden box`, and `get clay cup from wooden box`. Portable objects use the
existing take/drop/give/put commands. Only portable objects can be placed inside a
generated container; nested containers are excluded. Inventory displays item names.

Drafts are private to their creating admin, persist across reconnects, and share
the ten-pending-draft limit with single-room proposals. Return to the generation
origin to approve. Approval revalidates the complete draft, both origin and attachment
context, requested limits, and room-name uniqueness. A changed world makes the draft
stale. Repeated approval returns the existing result. Rejection cannot undo an
approved neighborhood. Reject and generate again to revise a draft.

Publication creates the buildings, rooms, exits, shared doors, and objects in one
transaction. Gameplay takes a shared world lock while loading and saving state;
publication takes the exclusive lock. Provider calls hold neither a transaction nor
a world lock. Newly published rooms enter each character's map only upon visiting.
Maps remain schematic and do not display building outlines or door state.

## Provider and configuration

Generation uses the existing admin-only `AI_WORLD_GENERATION_ENABLED` flag and
shared account allowance, provider attempt limit, and concurrency limit. One
dispatched attempt costs one unit even when the response is invalid or times out.
Pre-dispatch validation and capacity refusals are free. Preview, approval, and
rejection make no AI call. Turning generation off still allows preview and rejection.

```env
AI_NEIGHBORHOOD_TIMEOUT_SECONDS=60
AI_NEIGHBORHOOD_MAX_OUTPUT_TOKENS=8192
```

The timeout is bounded at 120 seconds and output at 16,384 tokens. Other AI features
retain their existing settings. Serialized input is limited to 8 KiB and the complete
HTTP response to 64 KiB. There are no automatic retries. Live AI remains restricted
to local development.

Only the brief, origin name, attachment name/description, chosen compass direction,
and room/building limits go to the provider. Character IDs, private memories, inventory,
and the full map are excluded. The adapter uses strict
[OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)
and validates relationships and budgets again locally. Schema compliance cannot
judge literary quality or setting consistency; admins review the text before approval.

The fake provider returns Cedar Lane with a fixed stone bench. When room and building
budgets permit, it adds Cedar Workroom, a cedar door, and a wooden box containing a
clay cup. Its names are deterministic, so a second approval in the same world conflicts
with the existing names. Use isolated test databases for repeated demonstrations.

## Migration and recovery

Migration `0014` adds buildings, doors, item portability, and version-2 proposal
payloads. Existing items remain portable; existing world layouts are preserved.
Take and verify a [backup](BACKUPS.md) before migrating. A downgrade refuses to
discard version-2 proposals; after neighborhood generation, recovery requires a
compatible backup and code version, not a destructive rollback.

## Validation

September 11, 2026 (local time):

- Backend lint, type checking (54 source files), and all 368 unit/integration
  tests passed, exit 0; coverage 93%. Two existing dependency deprecation
  warnings remain. The focused run caught inventory displaying generated UUIDs;
  inventory now uses item names and the full suite verifies the fix.
- Frontend lint, type checking, all 23 tests, and build passed, exit 0.
- All 13 Playwright workflows passed on a fresh isolated world, exit 0, including
  neighborhood preview/reconnect/approval, discovery, shared door notifications,
  container interaction, and inventory persistence. An initial run passed 12 and
  timed out in the existing item workflow with a slow-client disconnect while
  other tests/builds were running. The clean rerun used unchanged tests, worker
  count, and timeouts.
- Production-like configuration validation, hardened image builds, and local
  application builds passed, exit 0.
- The isolated migration check passed, exit 0: legacy rooms, items, discoveries,
  and version-1 proposals survive upgrade; downgrade/upgrade works before version-2
  drafts exist; a downgrade with a version-2 draft fails atomically as intended.
  The check's first attempt exposed a masked connection URL in the harness,
  corrected before rerunning. See `scripts/check-neighborhood-migration.py`.
- Load smoke passed, exit 0: 10 users for 30 seconds, zero failures in 263 measured
  commands, p95 776.69 ms. Authoritative-state invariant checks passed, exit 0.
- Backup `backups/pre-neighborhood/muddb-20260912T003723975Z-736bf505.dump`
  was created and restored in isolation, exit 0: revision `0013`, 10 rooms,
  11 players, 2 NPC memories. The backup commands used a process-only PowerShell
  execution-policy override.
- Local deployment passed, exit 0; backend and frontend are healthy. Revision
  `0014` is active, retaining 10 rooms and 11 players. Generation is enabled with
  the 60-second timeout and 8,192-token limit. Normal development source mounts
  are restored. No live AI calls were made and no local neighborhoods were
  generated during validation.
