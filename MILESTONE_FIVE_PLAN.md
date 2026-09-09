# Milestone Five — Controlled AI World Generation

## Status and goal

Planned; no M5 implementation or deployment is claimed. M4 is deployed and working,
as confirmed by the project owner on September 8, 2026. Local nightly database
backups and isolated restore verification are available; a second backup location
is deferred until non-local storage is available.

Deliver the first small generated area as **one new room with a bidirectional
connection to an existing room**. An admin requests, previews, and explicitly
approves it. Ordinary movement never triggers generation. The engine owns IDs,
geography, validation, and persistence; AI supplies bounded descriptive content.
This is the first increment of the specification's broader small-area generation
milestone, not a multi-room region generator.

## Admin workflow

Proposed command syntax, implemented through the existing authenticated WebSocket:

```text
/world propose north A quiet clearing with mossy stones
/world proposals
/world preview <proposal-id>
/world approve <proposal-id>
/world reject <proposal-id>
```

- `propose` anchors the request to the admin character's current room. Accept
  north/south/east/west/up/down and their existing short aliases. The selected
  direction must be unused. Preserve the brief's case and punctuation.
- Example: stand in Forest and propose north. Preview shows Forest → north →
  the proposed clearing, and clearing → south → Forest. Town Square's four
  horizontal exits are already occupied and cannot be replaced.
- Preview shows the full proposal ID, source ID/name, exact proposed name and
  description, both planned exits, status, and approval/rejection syntax. It is
  labeled as a draft and does not alter room state or move the admin.
- `proposals` lists the caller's latest 20 proposals, newest first, with IDs and
  statuses. A known ID remains retrievable through `preview` after restart.
- Only the creating admin can preview, approve, or reject a proposal in this
  increment. Every command rechecks current account role and session validity.
  Non-admin users cannot access proposal details or invoke these operations.
- Approval requires the creator to be back in the source room. It revalidates
  current conditions; a draft does not reserve an exit. Rejection is permitted
  from any room. Approval and rejection make no provider calls.
- Approved rooms become available to all players through normal `look` and
  movement. They persist across reload, backend restart, and world seeding.

## Scope and limits

- One generated room and exactly two reciprocal exits per approval.
- No generated items, NPCs, quests, regions, mechanics, extra connections, edits
  to existing rooms, room deletion, automatic expansion, or in-game restore.
- No draft editing: reject and request a new proposal. Previewed content is
  immutable so approval always refers to the exact content the admin reviewed.
- Command-first text output; no new frontend panel or transport is required.
- Proposed `AI_WORLD_GENERATION_ENABLED=false` feature flag. When disabled,
  proposal creation and approval are blocked; preview/list/reject remain usable.
- Real generation remains development-only, matching existing real-provider
  restrictions. Add a deterministic fake and mocked adapter contract coverage.
- One attempted generation consumes one unit from the initiating account's
  shared persistent allowance. Invalid syntax, unauthorized calls, occupied exits,
  and capacity rejection before provider dispatch consume no unit. Once dispatched,
  failed attempts count; no retry, interpretation, or narration call is added.
- Initial limits: 400-character brief, 1–100-character name, 1–2,000-character
  description with up to five sentences, 8,192 UTF-8 bytes of serialized context,
  and ten pending proposals
  per creator. Enforce pending capacity atomically, including concurrent requests.
- Reuse provider timeout, response-byte, concurrency, and attempt controls. Add an
  explicit generation-only output-token setting, initially 1,024 tokens, to support
  richer descriptions without changing interpretation or NPC budgets. Character
  and token limits are distinct; oversized/incomplete output fails safely without
  truncating prose. Provider work holds no game lock or database transaction.

## Description quality: set the mood

The owner requested longer, atmospheric descriptions on September 8, 2026. Give
each generated room a sense of place, using up to five sentences when needed.
Use concrete sensory details: the quality of light, nearby sounds, temperature,
texture, scent, and signs of age or habitation. Select details that fit the place;
not every description needs all five senses or all five sentences. Favor specific,
evocative language over stock fantasy adjectives and repetitive purple prose.

Establish the scene, develop a few distinctive details, and leave a memorable
final impression. Describe the surroundings without dictating the player's
feelings, thoughts, or actions. Ambient details do not introduce usable items,
active weather mechanics, NPCs, hazards, rewards, or unapproved routes. Do not
claim a time of day or changing weather supplied by a simulation that does not
exist. Keep approved descriptions stable between visits.

Example five-sentence description:

> The forest opens into a small clearing where pale light rests on a ring of
> moss-covered stones. Water beads along their weathered faces and gathers in
> the dark hollows between them. The air smells of damp earth and cedar, cool
> beneath the shelter of the surrounding branches. Somewhere beyond the clearing,
> a bird calls once, then falls silent. Even the wind seems quieter here.

Preview must show the complete prose without clipping; the normal room display
must preserve it too. Enforce the five-sentence ceiling through a documented,
deterministic sentence-boundary validator, with tests for punctuation, quoted
text, and common abbreviations. Reject overlong output rather than cutting it
mid-sentence. Human preview remains the check for mood, coherence, and unsupported
claims; structural tests alone cannot establish literary quality.

## Provider contract and validation

Strict output schema, with extra fields forbidden:

```json
{"name": "Mossy Clearing", "description": "The forest opens into a small clearing where pale light rests on a ring of moss-covered stones. Water beads along their weathered faces and gathers in the dark hollows between them. The air smells of damp earth and cedar, cool beneath the shelter of the surrounding branches. Somewhere beyond the clearing, a bird calls once, then falls silent. Even the wind seems quieter here."}
```

The provider receives only the brief, source room's approved name/description,
the selected outward and return directions, and fixed content constraints. Do
not send player identities, inventory, NPC memories, secrets, account data,
credentials, other drafts, or the full world. Treat briefs and existing prose as
untrusted text, never instructions authorizing tools or state changes.

Validate required fields, exact types, trimmed nonempty strings, character/byte
limits, and prohibited control characters. Render plain text using existing React
escaping. Reject a proposed name that case-insensitively duplicates an existing
room name; repeat that check at approval under serialized world-writing access.
Generate room and proposal UUIDs server-side; room UUIDs fit the existing 50-character
ID column. Providers cannot supply IDs, SQL, exits, capabilities, or rewards.

The server maps opposite directions deterministically. Foreign keys and exit
uniqueness remain database backstops. Structural validation cannot establish
whether prose fits the setting or implies an unsupported object; admin review
must assess those points before approval. Preview distinguishes descriptive prose
from the actual room/exit changes, and warns that no interactable objects are added.

## Persistence and concurrent operations

Add an Alembic migration for `world_proposals`; select the next migration revision
at implementation time. Keep canonical data in existing `rooms` and `room_exits`.
Drafts never enter those tables or player-visible world snapshots.

Store server-generated ID, creator account reference, source room reference,
source context fingerprint, direction, immutable validated content, schema version,
creation/decision timestamps, status, and resulting room ID. Use constrained
statuses (`pending`, `approved`, `rejected`, `stale`), foreign keys, and nullable
result ID consistent with status. Preserve a minimal decision history; defer draft
purging. Do not retain raw provider responses or the original brief after generation.
Retain creator attribution if an account is later deleted (nullable reference).

Generation flow:

1. Authenticate and validate source, direction, brief, quota, and pending capacity.
2. Read bounded context, close the transaction, and request the provider response.
3. Validate the response. In a short transaction, lock the creator account and
   recheck role, session, source location/context, feature flag, exit availability,
   and pending capacity before inserting the immutable draft. Concurrent excess
   responses are discarded safely; dispatched attempts still count.

Approval flow, entirely in one short transaction:

1. Recheck role/session/feature flag. Lock creator account, player, then proposal
   in a documented order compatible with existing account/player operations.
2. Require matching creator, pending status, and current source location. Repeated
   approval of an approved proposal returns its existing room ID without writes.
3. Acquire a transaction-scoped world-writing advisory lock shared by M5 approvals;
   recheck source context, name uniqueness, and selected exit. Document that future
   room-editing operations must follow the same serialization contract. Startup
   seeding remains insert-only; exit uniqueness still prevents overwriting.
4. Mark changed source context or occupied exit as stale with no world writes.
   Name conflicts also invalidate the draft. Ask for a new proposal.
5. Insert the room and reciprocal exits, then mark the proposal approved with its
   result ID. Any unexpected failure rolls back all world/proposal writes. Map
   database constraint conflicts to a safe conflict response, never partial success.
6. After commit, notify players currently in the source room that an exit is
   available through the existing room-event path. A failed notification cannot
   undo committed geography; the next `look` or reconnect reads canonical state.

Repeated rejection is harmless. Approved proposals cannot be rejected or undone
through this feature. Approval/rejection races must produce one terminal outcome.
No player is moved automatically and no long-lived world cache may hide new rooms.

## Affected modules

- `backend/app/commands/parser.py` and `services/game.py`: explicit `/world`
  routing, admin-only help, preservation of brief text, and no AI fallback routing.
- New domain/schema, model, repository, and generation service modules: immutable
  proposals, validation, authorization, and atomic approval. Keep SQL out of the
  parser and provider adapters; keep pure validation independently testable.
- `backend/app/ai/provider.py`, fake/real adapters, factory, and config: generation
  interface, bounded context, structured schema, feature flag, shared budgets.
- Existing room repositories and multiplayer delivery: verify generated rooms load
  from PostgreSQL and newly committed exits appear to connected players.
- Alembic, environment templates, Compose configuration, backend tests, and E2E
  coverage. Update help, README, AI usage docs, roadmap, and this validation record.

## Delivery sequence and acceptance tests

### 1. Deterministic proposal and approval core

- [ ] Add schema/migration and pure validators with invalid-input cases.
- [ ] Accept atmospheric descriptions up to five sentences and 2,000 characters;
  reject longer responses and verify full prose survives persistence and display.
- [ ] Implement persistence and approval using authored fixture proposals.
- [ ] Verify no draft changes rooms, movement, or player-visible state.
- [ ] Verify atomic room/two-exit creation, persistence after seeding/restart, and
  absence of orphan rooms after a forced insertion failure.
- [ ] Verify simultaneous approvals for one exit, repeated approval, approve/reject
  races, occupied exits, duplicate names, changed context, and creator isolation.

### 2. Provider generation and admin commands

- [ ] Add fake generation and mocked real-provider contract tests; no paid test calls.
- [ ] Verify bounded context excludes unrelated/secret data and extra response fields.
- [ ] Verify disabled feature, revoked admin/session, movement during generation,
  malformed replies, timeout, capacity races, quota accounting, and provider failure.
- [ ] Verify `/world` bypasses interpretation/narration and all commands enforce roles.
- [ ] Verify draft list/preview, approval/rejection, and actionable conflict messages.

### 3. Multiplayer experience and deployment readiness

- [ ] Browser workflow: admin proposes from Forest, previews unchanged geography,
  approves, and a second player traverses the new exit and returns.
- [ ] Browser workflow: non-admin denial and draft recovery after reconnect.
- [ ] Check privacy, escaped text, source-room notifications, and normal commands.
- [ ] Run the complete required deployment gate, including load smoke, and record
  actual command exit codes. Take a current database backup before live migrations.
- [ ] Deploy locally only after the gate passes; separately evaluate real generation
  quality using the configured development provider and explicitly record results.

## Definition of done

An authorized admin can generate, review, and approve one connected room; other
players can enter and return, and the room survives restart. Invalid, unauthorized,
stale, failed, and repeated operations cannot create duplicates or partial world
state. Tests establish isolation and concurrency behavior. Documentation records
the implemented scope, passing gate, backup, and local deployment separately from
any real-provider quality assessment. No M5 tests have been run for this plan-only
change.
