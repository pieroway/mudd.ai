# Item system implementation

## Inspection

- `domain/item_template.py` and migration `0018` already separate reusable templates
  from instances. `domain/item.py` deep-copies defaults and stores physical metadata.
- `repositories/game.py` loads and saves instance state, condition, discovery,
  relationships, quantity, and provenance, but does not persist new/deleted instances.
- `engine/executor.py` implements the original item verbs using legacy booleans.
  It does not yet enforce capabilities, aliases, discovery, hands, fit, or locks.
- `commands/parser.py` recognizes the original commands and selected tool interactions.
- `domain/client_state.py` and `InventoryPanel.tsx` expose inventory IDs and names only.
- Neighborhood generation validates fixed/portable/container objects and publishes
  atomically, but does not yet select templates or validate lock/key dependencies.

## Plan

1. Preserve legacy items and existing command behavior. Add a validated catalogue
   for every specified template, with detailed configurations for the priority set.
2. Add capability-based deterministic interactions, recursive accessibility,
   viewer-relative descriptions, discovery, hands/equipment, surfaces, physical
   constraints, locks, damage/repair, lighting, consumables, stacks, attachments,
   occupancy, readable parts, and practical vessel interactions.
3. Persist player condition/posture and room conditions with additive migration
   `0019`. Reuse instance JSON relationships and retain exactly one physical location.
   Save newly created instances and deletions transactionally.
4. Add lock/key dependency validation and deterministic key provisioning. Expose
   admin-only creation/inspection; extend generated objects through bounded template
   selection rather than arbitrary code or capabilities.
5. Extend the player snapshot and inventory panel with safe contextual text,
   visible state, contents, actions, held/equipped locations, and discovered details.
6. Cover priority acceptance flows, privacy, persistence, solvability, schema
   validation, legacy compatibility, and browser integration. Run required gates.

## Compatibility choices

Existing authored objects stay in place and retain their IDs and state. Templates
are inserted idempotently; no world reset is required. Ownership is recorded
separately from physical possession. Floors, maps, narration, and building drafts
remain independent of item authority. No real AI calls are used in tests.

Capabilities provide practical deterministic rules. Features requiring absent
systems (combat, a spell engine, NPC trading, cooperative action sessions) must fail
explicitly rather than fabricate effects or success. Administrator visibility is
available only through authenticated admin commands, never player snapshots.

## Verification

The catalogue was compared directly with section 10 of the specification:
159 required IDs, 159 registered templates, no missing entries.

Focused verification passed 237 command/AI/neighborhood tests and then 15 item
acceptance/persistence tests. Frontend lint, type checking, build, and 39 tests passed.
An initial complete backend run passed 456 tests and found one old fixture that
inserted an already-seeded catalogue ID. The fixture now uses its own ID and its
persistence test passed. Complete final-gate results are recorded below.

## Bug regression audit

The charter's reproduce/fix/verify sequence was not consistently followed during
the initial feature implementation. Further feature additions were paused for a
focused bug audit. These new tests were each executed and observed failing before
their fixes, and the identical five-test run subsequently passed:

- Nested insertion must respect every ancestor container's weight limit.
- An ambiguous template name must not select an arbitrary instance through legacy
  command fallback.
- Wielding must respect the template's declared equipment slots.
- Legacy portable objects must not silently gain the wieldable capability.
- Filling a carried vessel must account for liquid weight and reject the action
  before changing either vessel when carrying limits would be exceeded.

The earlier hidden-key concealment bug was also demonstrated by a failing
acceptance test before its fix. Browser assertion updates for intentional map,
narration, help, and contextual-inventory changes are test maintenance, not gameplay
bug fixes. Browser harness races are addressed in the browser layer.

Parallel browser testing subsequently exposed cross-player dependency checks that
blocked unrelated movement, plus missing room IDs and torchlight text in contextual
look output. Four focused cases (connected and isolated players, room IDs, and
torchlight) were observed failing before the fixes and passing afterward. World
solvability now uses physical regions and actual player-holder locations; ordinary
key-use permission remains actor-specific. A single-worker browser run cannot
replace this parallel multiplayer regression coverage.

A separate legacy-tool privacy reproduction demonstrated that fallback tool
selection could choose a hidden item. Its test failed before the visibility fix
and passed afterward, together with the surrounding item/legacy regressions.
The post-fix wider run passed 258 tests; the parallel browser rerun passed all 16.
The live pre-deployment baseline was migration `0018`, zero templates, and 69 item
instances. Catalogue seeding adds definitions without creating replacement items.

An approval-preview regression was also demonstrated before its fix: generated
keys were absent from the displayed object count and review details. Preview now
uses the same materialized instances as publication and lists templates, actual
portability, locked state, key locations/targets, and discovery clues. No deployment
was allowed while this approval information was incomplete.
The associated provenance check also failed before its fix: legacy-shaped AI
objects now retain `ai_generated` provenance just like template-backed objects.

The complete gate's smoke stage found a real read-path regression: p95 command
latency was 2.06 seconds against the existing 1-second smoke budget. A focused
test then demonstrated unnecessary dependency on an unreferenced template.
World reads now fetch and validate only templates referenced by actual instances.
The focused 40-test item/persistence run passed; the unchanged smoke rerun passed
with p95 826.74 ms and authoritative-state invariants intact. No thresholds or
checks were relaxed. The complete gate was subsequently run with this optimization.

A browser-harness cleanup assertion demonstrated that the duplicate-login test
left two manually created browser contexts open. It failed with an expected count
of zero and an actual count of two, then passed after `finally` cleanup was added.
Failed browser runs now retain backend logs before isolated-stack cleanup. No
connection limits, test timeouts, retries, or production behavior were loosened.

Focused tests were not substituted for the complete regression/deployment gate.

## Final verified result

`cmd /c scripts\deploy.bat` completed successfully with exit code 0.

- Backend: 470 tests passed; lint and type checking passed.
- Frontend: 39 tests passed; lint, type checking, and build passed.
- Production configuration validation and application image builds passed.
- Parallel Playwright: all 16 tests passed.
- Smoke load: 10 users for 30 seconds, p95 command latency 545.15 ms; the existing
  thresholds and authoritative-state invariant checks passed unchanged.
- The normal backend, frontend, PostgreSQL, and Redis services are healthy.
- Live database: migration `0019`, 159 templates, and 69 item instances. The instance
  count matches the pre-deployment baseline; no world reset or replacement occurred.
- The visible Windows browser option was separately verified with 16 passing tests.
- The item specification's heading-spacing check passed without MD022 violations.

The health data/effect foundation does not add character damage, combat, NPC
commerce/persuasion, a magic system, or coordinated multi-occupant vehicle travel.
Those remain separate gameplay increments. The next useful increment is an
authoritative character-health/damage flow with a player-visible status command.
