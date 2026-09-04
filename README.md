# AI-Enhanced MUD

A persistent multiplayer text-based game (MUD) with a deterministic authoritative game engine and controlled AI layers.

**Status:** Milestone Two — AI command interpretation in progress

## Development with Codex

This project is being developed with help from OpenAI Codex. Codex assists with
implementing features, writing and updating tests, diagnosing failures, and
maintaining documentation. The project owner directs the work, reviews the
changes, and remains responsible for the architecture and final code.

AI-assisted contributions follow the same project rules as every other change:
the deterministic game engine owns authoritative state, generated code is
reviewed, and the complete test gate must pass before deployment.

## Quick Start

### Prerequisites
- Docker Desktop (includes Docker and Docker Compose)
- Git

### First Time Setup

```bash
# Clone the repository
git clone https://github.com/yourusername/mudd.ai.git
cd mudd.ai

# Copy environment template
cp .env.example .env

# Build and start services
make dev
```

### Access the Game

- **Frontend (MUD Client):** http://localhost:5173
- **Backend (API):** http://localhost:8000
- **Health Check:** http://localhost:8000/health
- **Database (psql):** `psql -h localhost -U muduser -d muddb` (password: mudpass)

PostgreSQL is exposed only on the host loopback interface for local development.
Redis is available only to containers on the Compose network and has no host port.

## Development Commands

```bash
# Start development environment
make dev

# Stop all services
make down

# Run unit tests (backend)
make test

# Audit Python and Node dependencies
make audit

# Run E2E tests (Playwright)
make e2e

# Full pipeline: test, build, deploy
make deploy

# View backend logs
make logs

# Clean up containers and volumes
make clean
```

The dependency audit blocks on every known Python advisory and on high or
critical Node advisories. A registry or advisory-service error also fails the
audit because the dependency state could not be verified. GitHub Actions runs
it when dependency inputs change, every Monday, and on manual request. It is
kept separate from deployment so advisory-service outages cannot prevent an
otherwise verified release; run `make audit` before an exceptional manual
deployment that did not pass through the protected branch workflow.

## Project Structure

```
mudd.ai/
├── backend/              # Python FastAPI backend
│   ├── app/             # Application code
│   ├── tests/           # Unit and integration tests
│   ├── alembic/         # Database migrations
│   ├── Dockerfile
│   └── pyproject.toml   # Dependencies
│
├── frontend/            # TypeScript React client
│   ├── src/
│   │   ├── components/  # React components
│   │   ├── styles/      # CSS
│   │   └── App.tsx      # Main app
│   ├── Dockerfile
│   └── package.json
│
├── e2e/                 # Playwright end-to-end tests
│   ├── tests/
│   └── playwright.config.ts
│
├── scripts/             # Utility scripts
├── compose.yaml         # Development Docker Compose
├── compose.test.yaml    # Test Docker Compose
├── Makefile            # Common commands
├── README.md
├── AGENTS.md           # AI agent guidance
├── CODEX.md           # Codex project instructions
└── AI_MUD_CODEX_PROJECT_PROMPT.md  # Full specification
```

## Architecture Overview

The game consists of layers:

1. **Domain** — Pure game logic (rooms, players, items)
2. **Engine** — Command execution and validation
3. **Commands** — Parsing and routing
4. **Services** — Orchestration (game service + narration)
5. **API** — FastAPI routes and WebSocket
6. **Database** — PostgreSQL (authoritative store)
7. **AI** — Abstraction layer (FakeAIProvider for development)

**Core Principle:** THE GAME ENGINE OWNS REALITY. AI may propose, interpret, or describe, but never directly decides authoritative game state.

## Database Setup

PostgreSQL runs in Docker. No local installation needed.

```bash
# Connect to the database
psql -h localhost -U muduser -d muddb

# Run migrations manually (backend startup also runs this automatically)
docker compose exec backend alembic upgrade head

# Reset the database
docker compose down -v  # Removes volumes
make dev  # Rebuilds fresh
```

Player location and inventory are stored in PostgreSQL. Usernames are normalized
case-insensitively and must be unique. Milestone One does not provide passwords or
account authentication, so usernames are persistent identities but are not yet secure accounts.

## Testing

### Unit Tests (Backend)

```bash
# Run all tests
make test

# Run specific test file
docker compose -f compose.test.yaml run --rm backend_test pytest tests/test_parser.py -v

# Run with coverage
docker compose -f compose.test.yaml run --rm backend_test pytest --cov=app -v
```

### E2E Tests (Playwright)

```bash
make e2e
```

## Configuration

Edit `.env` to customize:

```env
APP_ENV=development              # development, test, production
LOG_LEVEL=INFO                   # DEBUG, INFO, WARNING, ERROR
TRUSTED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
MAX_COMMAND_BYTES=4096          # UTF-8 command size and transport-frame limit
COMMAND_RATE_LIMIT=10           # Commands allowed per client/window
COMMAND_RATE_WINDOW_SECONDS=1
MAX_WEBSOCKET_CONNECTIONS=250   # Per backend process
CONNECTION_ATTEMPT_LIMIT=60     # Attempts per source address/window
CONNECTION_ATTEMPT_WINDOW_SECONDS=60
MAX_TRACKED_CLIENT_ADDRESSES=10000
OUTBOUND_SEND_TIMEOUT_SECONDS=2

DATABASE_URL=postgresql+...      # Database connection
REDIS_URL=redis://...            # Redis connection

AI_PROVIDER=fake                 # fake, anthropic, openai
AI_NARRATION_ENABLED=false       # Enable AI narration
```

## Development Workflow

1. **Make a small change** to backend or frontend
2. **Run tests** — `make test`
3. **Check the app** — visit http://localhost:5173
4. **Commit and push** when tests pass

**Never deploy without passing tests.**

## Troubleshooting

### Containers won't start
```bash
docker compose down -v
docker system prune -f
make dev
```

### Database connection error
```bash
docker compose exec postgres psql -U muduser -d muddb -c "SELECT 1"
```

### Port already in use
```bash
# Kill process on port 8000 (backend)
lsof -ti:8000 | xargs kill -9

# Kill process on port 5173 (frontend)
lsof -ti:5173 | xargs kill -9

make dev
```

### Rebuild containers
```bash
docker compose build --no-cache
make dev
```

## Milestones

- **M1** (Complete): Deterministic 5-room MUD with terminal client
- **M2** (Current): AI natural-language command interpretation
- **M3**: AI narration
- **M4**: One AI-powered NPC with personality/memory
- **M5**: Controlled AI world generation

## Documentation

- [AI_MUD_CODEX_PROJECT_PROMPT.md](AI_MUD_CODEX_PROJECT_PROMPT.md) — Complete specification
- [MILESTONE_ONE_PLAN.md](MILESTONE_ONE_PLAN.md) — M1 roadmap
- [MILESTONE_TWO_PLAN.md](MILESTONE_TWO_PLAN.md) — Current M2 delivery plan
- [Security review](docs/SECURITY_REVIEW_2026-09-02.md) — Open risks and remediation status
- [AGENTS.md](AGENTS.md) — AI agent operating guide
- [CODEX.md](CODEX.md) — Codex project instructions

## License

TBD

## Contributing

See contributing guide (to be created).
