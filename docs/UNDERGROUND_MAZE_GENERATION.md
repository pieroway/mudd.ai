# MUDD.AI — Procedural 3D Underground Maze Generator

## Generate a maze

An administrator can create a maze from the current room. The entrance requires a
free exit in the selected direction. This example generates a five-level mine.

```text
/world generate maze --theme abandoned-mine --rooms 250 --levels 5 --seed 7421 --loops 15 --direction down
```

The command supports 1–500 rooms, 1–20 levels, and the themes
`abandoned-mine`, `natural-caves`, and `catacombs`. The loop percentage
controls how often unused neighboring passages are opened. An omitted seed is
generated and reported in the command response. Region-relative coordinates,
configuration, and generator version are saved on the rooms. Vertical routes
can include shared, operable trapdoors.

Use `--secrets`, `--locks`, and `--jams` to set the percentage of optional
loops with concealed, locked, and jammed doors. The defaults are 15, 20, and
10 respectively. These conditions can overlap. Required passages are free of
these obstacles. Chamber entrances and level landings contain wooden crates.

Search a room to reveal both sides of a concealed passage for everyone. If
the maze generates locked or jammed doors, its entry chamber contains a
passage key or crowbar as needed. For example, in an abandoned mine:

```text
search
unlock east door with mine passage key
pry east door with iron crowbar
open east door
east
```

Add `--railways true --minecarts true --rail-density 65` to build a connected
railway from the entry chamber and place one braked cart there. Density is the
percentage of the maze's required passages to equip with track. Use
`--minecarts false` for tracks without a cart.

On a railway, use `/rail status` to see connected tracks, switch alignment,
and the cart brake. At a junction, use `/rail switch east` (or another
connected direction) before moving the cart.

```text
examine minecart
put iron crowbar in minecart
board minecart
/rail brake off
/rail ride east
/rail brake on
leave
take iron crowbar from minecart
```

Use `/rail push up` or `/rail pull up` with an empty seat and the brake
released to move the cart uphill. A cart carries one rider at a time. Shut
doors, broken switches, other carts, and excess load block movement. Repair a
damaged cart with a suitable carried tool, such as a hammer.

The phases below describe the complete feature specification.

## Objective

Implement a reusable procedural underground maze generation system within the existing MUDD.AI project.

The system must generate persistent, interconnected, three-dimensional underground environments with rich atmospheric descriptions and meaningful player interactions.

**Do not create a separate game or independent application.** Integrate directly with the existing MUDD.AI architecture.

## Phase 1 — Inspect the project

Before writing code:

1. Identify the current room, world, region, exit, item, movement, interaction, and persistence models.
2. Examine existing procedural generation and world expansion mechanisms.
3. Identify the command parser and administrative permissions.
4. Examine the existing test infrastructure, including pytest, Playwright, and CI.
5. Reuse existing models, services, APIs, and item templates whenever possible.
6. Identify architectural conflicts or missing abstractions.

Produce a short implementation plan, then proceed with the implementation.

Avoid unnecessary refactoring and preserve existing game behavior.

## Phase 2 — Generator command

Implement an administrator-only command supporting arguments equivalent to:

```text
generate maze
  --theme abandoned-mine
  --rooms 250
  --levels 5
  --seed 7421
  --difficulty medium
  --secrets 15
  --railways true
  --minecarts true
  --ambiance rich
```

Adapt the syntax to the project's existing command system.

Support optional parameters for:

- Number of rooms
- Number of vertical levels
- Minimum and maximum room dimensions
- Maze complexity and branching
- Loop density
- Secret passage frequency
- Locked door frequency
- Railway density
- Minecart frequency
- Environmental hazards
- Description richness
- Random generation seed
- Connection to an existing world location

Validate arguments and impose configurable safety limits.

## Phase 3 — True 3D spatial generation

Generate a connected spatial graph with persistent X, Y, and Z coordinates.

Include:

- Horizontal and vertical tunnels
- Chambers of different shapes and sizes
- Interconnected underground levels
- Spiral staircases
- Straight staircases
- Ladders
- Trapdoors
- Vertical shafts
- Bridges and ledges
- Large multi-level caverns
- Loops and alternative routes
- Dead ends and hidden connections

Prevent invalid room overlaps and impossible geometry unless explicitly supported by the world model.

Distinguish physical coordinates from navigational graph connections.

Rooms must not be constrained to a rigid square grid if the existing architecture permits more flexible geometry.

Ensure the generated environment is traversable.

## Phase 4 — Doors and passageways

Generate doors with persistent properties and state.

Supported features should include:

- Wooden doors
- Iron doors
- Reinforced doors
- Locked doors
- Secret doors
- Rusted or jammed doors
- Portcullises
- Trapdoors
- Gates

Doors must be actual interactive entities, not simply text in room descriptions.

Both sides of a shared door must reference the same logical door state.

Generate compatible keys, switches, mechanisms, or alternative solutions for locked passages.

Ensure keys and required tools are reachable before the corresponding obstacle, unless the obstacle is intentionally optional.

Use existing MUDD.AI item and interaction systems.

## Phase 5 — Railway network

Implement connected railway segments as a separate but spatially integrated transport graph.

Generate:

- Straight and curved railway segments
- Junctions and switches
- Railway stations and loading platforms
- Inclined tracks
- Bridges
- Derailment hazards
- Abandoned sidings
- Buffer stops
- Underground rail tunnels

Rail segments must form physically valid connections.

A railway should not terminate unexpectedly inside a wall unless deliberately designed as a damaged or abandoned endpoint.

## Phase 6 — Functional minecarts

Create minecarts as interactive world objects.

Players should be able to:

- Examine a cart
- Push or pull it
- Enter or exit it
- Load or unload items
- Apply or release brakes
- Ride along connected tracks
- Operate railway switches
- Attempt to repair broken carts

Minecart movement must obey railway connectivity, track direction, slope, switches, and obstructions.

Movement must update actual game state and player location.

Use deterministic simulation rules for transport mechanics, not an LLM's invented movement results.

Support multi-user behavior, including preventing conflicting updates to a shared cart.

Avoid creating a complete physics engine unless the existing application requires one.

## Phase 7 — Rich procedural ambiance

Every generated location must receive a distinctive environmental identity.

Build descriptions from structured location properties.

Consider:

- Architecture and construction materials
- Geological characteristics
- Lighting and visibility
- Ambient sounds and echoes
- Air movement and temperature
- Water and moisture
- Odours
- Machinery
- Evidence of past inhabitants
- Signs of danger
- Connections to neighbouring locations
- Nearby visible objects
- Vertical depth
- Environmental history

Descriptions should be atmospheric and vivid, without becoming excessively long.

Avoid repetitive phrases and obvious procedural templates.

Use the project's existing AI/LLM infrastructure where appropriate for description authoring.

However, the AI must not invent items, exits, machinery, or interactable features that do not exist in authoritative game state.

Every mentioned interactable object should correspond to an existing entity or a deliberately non-interactive environmental detail.

Descriptions must change according to context:

- Whether a door is open or closed
- Whether a light source is present
- Whether machinery is operating
- Whether a minecart is approaching
- Whether a player is standing on a bridge or beneath it
- Whether a trapdoor is open
- Whether an object has been removed
- Whether the room has been flooded

Generate stable base descriptions and use contextual overlays or state-aware rendering to avoid unnecessary LLM calls on every player action.

## Phase 8 — Environmental interactions

Generate appropriate interactive objects such as:

- Levers
- Valves
- Chains
- Ropes
- Lamps
- Mining tools
- Crates and barrels
- Machinery
- Wooden supports
- Rail switches
- Water pumps
- Ladders
- Loose stones
- Hidden compartments

Reuse existing MUDD.AI item templates.

Ensure interactions produce meaningful state transitions and persist properly.

Where appropriate, connect objects to environmental mechanisms.

For example, pulling a lever might change railway alignment or open a gate.

## Phase 9 — Exploration and expansion

Support linking the generated maze to an existing room or region.

Allow expansion from unexplored boundaries while preserving existing geometry and world state.

Expansion must be deterministic where practical, respect occupied coordinates, and avoid overwriting explored areas.

Support maze generation for future themes including:

- Abandoned mines
- Natural caves
- Ancient catacombs
- Sewers
- Crypts
- Underground fortresses
- Forgotten cities

Keep the core topology generator independent from theme-specific content.

## Phase 10 — Persistence and repeatability

The generated environment must persist through server restarts.

A generator seed and identical configuration should produce identical initial topology, room attributes, and placed objects.

Separate generated initial state from subsequent player modifications.

Support transaction-safe generation and rollback on failure.

Avoid leaving orphaned rooms, doors, tracks, items, or partial regions.

Record useful generation metadata including seed, configuration, generated region identifier, and generator version.

## Phase 11 — Testing

Create comprehensive automated tests using the project's existing frameworks.

Include tests verifying:

1. Correct generated room counts and level constraints.
2. Deterministic generation from a seed.
3. Valid coordinate placement.
4. Complete reachability from the entrance.
5. Correct bidirectional connections.
6. Shared door state consistency.
7. Key and lock solvability.
8. Trapdoor and staircase connectivity.
9. Valid railway connections.
10. Railway switch operation.
11. Minecart movement and passenger handling.
12. Player and item persistence.
13. Consistent multi-user state.
14. Description accuracy relative to game state.
15. Safe expansion of existing environments.
16. No broken existing gameplay.
17. Generation failure recovery and rollback.
18. Correct permissions and invalid-argument handling.

Include integration tests using the real persistence layer.

Add Playwright tests where useful for administrative commands, navigation, and map rendering.

Add performance tests for large maze generation.

## Phase 12 — Administrative map

Integrate the generated region with MUDD.AI's existing administrative map.

Support displaying:

- All generated levels
- Individual depth levels
- Room coordinates
- Passage connections
- Staircases and trapdoors
- Locked passages
- Railway networks
- Minecart positions
- Hidden locations for administrators

Preserve ordinary players' fog-of-war and discovery restrictions.

If the current renderer cannot display true 3D, implement an appropriate level-by-level view without replacing the entire map system.

## Deliverables

- Integrated generator implementation
- Administrative generator command
- Reusable configuration and theme definitions
- Room, connection, and railway generation
- Functional generated interactions
- Automated tests
- Documentation and command examples
- Sample generated maze
- Performance results for a 250-room, five-level maze

## Implementation rules

- Inspect existing code before making architectural decisions.
- Reuse existing systems instead of duplicating them.
- Maintain compatibility with existing saved worlds.
- Do not modify unrelated functionality.
- Do not introduce dependencies without justification.
- Keep procedural algorithms separate from AI-generated narrative content.
- Preserve deterministic gameplay and persistent state.
- Keep the generator modular and testable.
- Run available tests and report failures.
- Do not claim unimplemented features are complete.

Implement in logical stages, validating each major subsystem before continuing.

At completion, report what was implemented, any limitations, tests executed, performance measurements, and the exact command for generating a maze.
