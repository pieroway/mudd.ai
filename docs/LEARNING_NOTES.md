# Learning Notes

Add a short explanation and a project example when a milestone introduces a
concept worth revisiting.

## Python and testing

- **Typed data at boundaries.** Pydantic validates the shape and size of data
  coming from an AI provider. The engine then checks whether the proposed
  action is legal in the current game state. [AI contracts](../backend/app/ai/models.py)
- **Fixtures and fake providers.** pytest fixtures seed a predictable world.
  The fake AI provider makes AI behavior predictable in tests without API calls.
  [Test fixtures](../backend/tests/conftest.py) · [Fake provider](../backend/app/ai/fake.py)
- **Regression tests.** A regression test turns a specific edge case into a
  repeatable check. The teleport test uses a room name with an apostrophe,
  accent, and parentheses to verify that command parsing preserves the name.
  [WebSocket integration tests](../backend/tests/integration/test_websocket.py)
- **Browser tests.** Playwright can verify what a player actually sees. The map
  tests measure label bounds at different zooms and check that Ctrl+wheel changes
  the viewed floor without moving the character. [Map browser tests](../e2e/tests/map-levels.spec.ts)

## Docker and Git

- **Isolated test stacks.** Compose gives tests their own database and services.
  The deployment gate runs tests, browser workflows, and a short concurrent
  load test before restarting the local game. [Test Compose](../compose.test.yaml) ·
  [Deployment gate](../scripts/deploy.bat)
- **Dependency audits.** Tests check behavior. An advisory scan checks installed
  versions against known vulnerabilities. The security review found a
  vulnerable Python TLS trust bundle even though gameplay tests passed.
  [Dependency audit script](../scripts/audit.bat)
- **Commit and push.** A commit records a change locally. A push sends commits
  to the remote branch. Separate commits for teleport, map changes, and
  sign-out make each feature easier to review and revert.

## FastAPI and WebSockets

- **Session identity and permissions.** FastAPI resolves a session cookie to
  an account and character. The server decides which actions that account
  can take. For example, a regular player can travel as a companion while
  the command caller needs a teleport role. [Authentication](../backend/app/services/auth.py) ·
  [Game commands](../backend/app/services/game.py)
- **State and events on a live connection.** A WebSocket carries commands,
  replies, and updates from other players. Group teleport sends companions
  both an arrival notice and their updated room and map state.
  [WebSocket endpoint](../backend/app/api/websocket.py)

## PostgreSQL and game architecture

- **Transactions and migrations.** A transaction commits related changes
  together. Group teleport writes the locations and discoveries together.
  A migration changes the database schema, such as adding the shared
  narration table. [Game commands](../backend/app/services/game.py) ·
  [Narration migration](../backend/alembic/versions/0023_narration_library.py)
- **Preview, validate, and publish.** World generation creates a draft.
  Approval checks it against current world state before saving canonical rooms
  and exits. This lets an operator review prose and topology before players
  encounter them. [World generation](WORLD_GENERATION.md)
- **Templates and instances.** An item template defines reusable properties.
  An instance has its own identity, location, and state. Two items made from
  one template can wear out independently. [Item templates](../backend/app/domain/item_template.py) ·
  [Persistence models](../backend/app/models/game.py)
- **Map state and map display.** The server decides which room data the browser
  can receive. The browser uses the room connections to place boxes, show
  floors, and zoom. Viewing an unvisited room in the privileged map leaves the
  player's discovery history intact. [Map guide](MAP.md)

## AI integration

- **World descriptions and narration.** Approved world descriptions are saved
  with the rooms, doors, or items they describe. Optional narration adds prose
  to a game outcome the engine already resolved. [World generation](WORLD_GENERATION.md) ·
  [Narration service](../backend/app/services/narration.py)
- **Shared cache and AI costs.** The library keys flourishes by the action,
  success flag, and exact outcome. The first miss can generate up to five
  variants in one request. Later hits choose a saved variant without spending
  another game AI unit. API billing also depends on input and output tokens.
  [Narration service](../backend/app/services/narration.py) ·
  [AI allowance](../backend/app/services/ai_usage.py)
