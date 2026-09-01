# Architecture

Browser client → HTTP/WebSocket API → command router → classic parser or AI intent parser → validator → authoritative game engine → PostgreSQL / Redis as appropriate → structured result → optional AI narrator → client.

Use a modular monolith first. Avoid premature microservices.

## Authority

PostgreSQL-backed game/domain state is canonical.

AI cannot directly decide or mutate rooms, exits, inventory, ownership, health, currency, quest completion, combat outcomes, shared environmental state, or NPC knowledge boundaries.

## Initial stack

Backend: Python, FastAPI, SQLAlchemy, Alembic, Pydantic, PostgreSQL, Redis when justified.

Frontend: TypeScript, React unless a simpler approach is clearly better, WebSockets.

Infrastructure: Docker, Docker Compose, Docker Desktop.

AI: provider abstraction, strict structured request/response models, FakeAIProvider for tests.
