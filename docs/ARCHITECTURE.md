# Architecture

Browser client → HTTP/WebSocket API → command router → classic parser or AI intent parser → validator → authoritative game engine → PostgreSQL / Redis as appropriate → structured result → optional AI narrator → client.

Game-output WebSocket messages include diagnostic metadata with a
`command_source` value of `classic` or `ai`. Clients may use this structured
field for diagnostics or presentation but must not infer it from transcript
text. The field describes interpretation only; it does not grant authority to
the AI provider.

Use a modular monolith first. Avoid premature microservices.

## Authority

PostgreSQL-backed game/domain state is canonical.

Rooms, exits, items, player location, and item ownership are persisted through
SQLAlchemy models managed by Alembic migrations. A normalized username uniquely
identifies a persistent player. Commands load domain objects, execute in the
deterministic engine, and persist the result within one database transaction.

Active username presence is currently enforced inside one backend process. Before
running multiple backend replicas, presence must move to Redis or another shared
lease mechanism. Usernames are not authenticated accounts until credentials or an
external identity provider are added.

AI cannot directly decide or mutate rooms, exits, inventory, ownership, health, currency, quest completion, combat outcomes, shared environmental state, or NPC knowledge boundaries.

## Initial stack

Backend: Python, FastAPI, SQLAlchemy, Alembic, Pydantic, PostgreSQL, Redis when justified.

Frontend: TypeScript, React unless a simpler approach is clearly better, WebSockets.

Infrastructure: Docker, Docker Compose, Docker Desktop.

AI: provider abstraction, strict structured request/response models, FakeAIProvider for tests.
