# Milestone One Implementation Plan — Deterministic MUD

## Executive Summary

Milestone One creates a **playable, deterministic MUD with no AI yet**. Players can:
- Connect via a browser-based terminal client
- Move through 5 connected rooms
- Examine items
- Manage inventory
- See other players in real-time

The game engine is fully authoritative. All tests must pass before deployment. The architecture is prepared for Milestone Two (AI command interpretation).

**Estimated scope:** ~2-3 weeks for a pair working full-time
**Key constraint:** No feature is done until tests pass AND code is deployed

---

## 1. Directory Structure

```
mudd.ai/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py              # FastAPI entry point
│   │   ├── config.py            # Settings (env vars)
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── websocket.py     # WebSocket handler
│   │   │   └── health.py        # GET /health
│   │   ├── commands/
│   │   │   ├── __init__.py
│   │   │   ├── parser.py        # Classic command parser
│   │   │   └── command.py       # Command models
│   │   ├── domain/
│   │   │   ├── __init__.py
│   │   │   ├── room.py          # Room entity
│   │   │   ├── player.py        # Player entity
│   │   │   ├── item.py          # Item entity
│   │   │   └── world.py         # World/region/geography
│   │   ├── engine/
│   │   │   ├── __init__.py
│   │   │   ├── executor.py      # Command execution
│   │   │   ├── validator.py     # Action validation
│   │   │   └── events.py        # Game events
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── player.py        # SQLAlchemy Player
│   │   │   ├── room.py          # SQLAlchemy Room
│   │   │   ├── item.py          # SQLAlchemy Item
│   │   │   └── base.py          # Base model with timestamps
│   │   ├── repositories/
│   │   │   ├── __init__.py
│   │   │   ├── player_repo.py
│   │   │   ├── room_repo.py
│   │   │   └── item_repo.py
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── game_service.py  # Orchestrates engine + narration
│   │   │   └── narration.py     # Convert results to prose
│   │   ├── db/
│   │   │   ├── __init__.py
│   │   │   ├── database.py      # SQLAlchemy setup, session factory
│   │   │   └── connection.py    # Connection pooling
│   │   └── ai/
│   │       ├── __init__.py
│   │       ├── provider.py      # Abstract AIProvider
│   │       └── fake.py          # FakeAIProvider for testing
│   │
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── conftest.py          # pytest fixtures
│   │   ├── test_parser.py       # Command parsing tests
│   │   ├── test_commands/
│   │   │   ├── __init__.py
│   │   │   ├── test_look.py
│   │   │   ├── test_movement.py
│   │   │   ├── test_inventory.py
│   │   │   └── test_items.py
│   │   ├── test_engine/
│   │   │   ├── __init__.py
│   │   │   ├── test_validator.py
│   │   │   ├── test_executor.py
│   │   │   └── test_events.py
│   │   ├── test_domain/
│   │   │   ├── __init__.py
│   │   │   ├── test_player.py
│   │   │   ├── test_room.py
│   │   │   └── test_item.py
│   │   ├── test_repositories/
│   │   │   ├── __init__.py
│   │   │   ├── test_player_repo.py
│   │   │   ├── test_room_repo.py
│   │   │   └── test_item_repo.py
│   │   ├── fixtures/
│   │   │   ├── __init__.py
│   │   │   ├── world.py         # Seeded test world
│   │   │   └── players.py       # Test player factories
│   │   └── integration/
│   │       ├── __init__.py
│   │       └── test_websocket.py # WebSocket integration tests
│   │
│   ├── alembic/
│   │   ├── env.py
│   │   ├── script.py.mako
│   │   └── versions/            # Empty initially
│   │
│   ├── pyproject.toml           # Dependencies, pytest config
│   ├── Dockerfile
│   ├── .dockerignore
│   └── README.md
│
├── frontend/
│   ├── src/
│   │   ├── main.tsx
│   │   ├── App.tsx
│   │   ├── vite-env.d.ts
│   │   ├── components/
│   │   │   ├── Terminal.tsx      # Main transcript + command input
│   │   │   ├── Transcript.tsx    # Scrollable output area
│   │   │   ├── CommandPrompt.tsx # Input field + autocomplete
│   │   │   └── PanelContainer.tsx # Prepared for future panels
│   │   ├── hooks/
│   │   │   ├── useWebSocket.ts   # WebSocket management
│   │   │   ├── useGameState.ts   # Local state for game info
│   │   │   └── useTerminal.ts    # Terminal command history
│   │   ├── services/
│   │   │   ├── websocket.ts      # WebSocket protocol
│   │   │   └── commands.ts       # Client-side command validation
│   │   ├── types/
│   │   │   ├── index.ts          # Shared TypeScript types
│   │   │   └── game.ts           # Game state types
│   │   └── styles/
│   │       └── index.css         # Terminal styling
│   │
│   ├── tests/
│   │   ├── __init__.ts
│   │   ├── setup.ts
│   │   ├── components/
│   │   │   └── Terminal.test.tsx
│   │   ├── hooks/
│   │   │   └── useWebSocket.test.ts
│   │   └── services/
│   │       └── commands.test.ts
│   │
│   ├── public/
│   │   └── index.html
│   │
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   ├── Dockerfile
│   └── .dockerignore
│
├── e2e/
│   ├── tests/
│   │   ├── auth.spec.ts         # Login/signup flows
│   │   ├── movement.spec.ts     # Navigate between rooms
│   │   ├── inventory.spec.ts    # Pick up/drop items
│   │   ├── examine.spec.ts      # Look at objects
│   │   ├── help.spec.ts         # Help command
│   │   ├── multiplayer.spec.ts  # Multiple players in same room
│   │   └── persistence.spec.ts  # Reconnect retains state
│   │
│   ├── fixtures/
│   │   ├── world.ts             # Seed test world
│   │   └── users.ts             # Test account factories
│   │
│   ├── playwright.config.ts
│   └── package.json
│
├── docker/
│   └── postgres-init.sql        # Initial DB schema (optional)
│
├── scripts/
│   ├── test.sh                  # Run unit tests with gate
│   ├── e2e.sh                   # Run Playwright tests
│   ├── deploy.sh                # Full pipeline
│   ├── reset-db.sh              # Reset test/dev database
│   └── seed-world.py            # Create initial rooms/items
│
├── compose.yaml                 # Development stack
├── compose.test.yaml            # Isolated test stack
├── Dockerfile.backend           # If needed separately
├── Dockerfile.frontend          # If needed separately
├── .env.example
├── Makefile
├── README.md                    # Developer onboarding
├── CLAUDE.md                    # Claude project instructions
├── AGENTS.md                    # AI agent guidance (✓ created)
└── AI_MUD_CLAUDE_PROJECT_PROMPT.md  # Full specification
```

---

## 2. Docker Services

### compose.yaml (Development)

```yaml
version: '3.9'

services:
  postgres:
    image: postgres:16-alpine
    ports:
      - "5432:5432"
    environment:
      POSTGRES_USER: muduser
      POSTGRES_PASSWORD: mudpass
      POSTGRES_DB: muddb
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U muduser"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: postgresql+asyncpg://muduser:mudpass@postgres:5432/muddb
      REDIS_URL: redis://redis:6379
      AI_PROVIDER: fake
      APP_ENV: development
      LOG_LEVEL: INFO
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    volumes:
      - ./backend:/app/backend
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 10s
      timeout: 5s
      retries: 5

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    ports:
      - "5173:5173"
    environment:
      VITE_API_URL: http://localhost:8000
    depends_on:
      - backend
    volumes:
      - ./frontend/src:/app/src
    command: npm run dev

volumes:
  postgres_data:
```

### compose.test.yaml (Isolated Testing)

```yaml
version: '3.9'

services:
  postgres_test:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: muduser
      POSTGRES_PASSWORD: mudpass
      POSTGRES_DB: muddb_test
    volumes:
      - /tmp/postgres_test:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U muduser"]
      interval: 5s
      timeout: 5s
      retries: 3

  redis_test:
    image: redis:7-alpine
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 5s
      retries: 3

  backend_test:
    build:
      context: ./backend
      dockerfile: Dockerfile
    environment:
      DATABASE_URL: postgresql+asyncpg://muduser:mudpass@postgres_test:5432/muddb_test
      REDIS_URL: redis://redis_test:6379
      AI_PROVIDER: fake
      APP_ENV: test
      LOG_LEVEL: WARNING
    depends_on:
      postgres_test:
        condition: service_healthy
      redis_test:
        condition: service_healthy
    command: pytest --cov=app --cov-report=term-missing -v

volumes:
  postgres_test:
```

---

## 3. Backend Architecture

### Core Layers

#### Layer 1: Domain (Game Rules)
- Pure business logic, no FastAPI/SQLAlchemy
- Room, Player, Item entities
- Validation rules
- Movement, inventory logic

#### Layer 2: Engine (Execution & Validation)
- Executes commands against domain
- Validates actions
- Generates structured game results
- No narration, no AI

#### Layer 3: Commands (Parsing & Routing)
- Classic parser (north, south, look, get, etc.)
- Parses input → Command model
- Routes to engine

#### Layer 4: Services (Orchestration)
- GameService: coordinates engine + narration
- NarrationService: converts results to prose
- No business logic here

#### Layer 5: API (FastAPI)
- WebSocket handler
- HTTP endpoints (login, health, etc.)
- No business logic

#### Layer 6: Database (Persistence)
- SQLAlchemy models
- Repositories (data access)
- Alembic migrations

#### Layer 7: AI (Provider Abstraction)
- Abstract AIProvider
- FakeAIProvider for development/testing
- Extensible for Claude/OpenAI later

### Example Data Flow

```
Browser Input: "north"
       |
       v
WebSocket Handler
       |
       v
Command Parser: "north" → Command(action="MOVE", direction="north")
       |
       v
Game Engine:
  - Validator: Is player in valid room? Is exit available?
  - Executor: Move player, generate event
  - Result: {"action": "MOVE", "success": true, "new_room_id": "..."}
       |
       v
Narration Service:
  "You walk north. The town square opens before you..."
       |
       v
WebSocket → Browser
```

---

## 4. Frontend Architecture

### Core Components

**Terminal (Main)**
```
┌──────────────────────────────────────┐
│           Transcript Area             │ ← Scrollable, read-only
│                                      │
│  Welcome to the MUD!                 │
│  You are in the Town Square.         │
│                                      │
│  [Optional Panel Area - Hidden]      │
├──────────────────────────────────────┤
│  > [command prompt]                  │ ← Command input with history
└──────────────────────────────────────┘
```

### State Management

**Authoritative Game State (from server):**
- Current room
- Player health/stats
- Inventory
- Visible NPCs
- Known map rooms
- Discovered exits

**Client UI State (local):**
- Transcript scroll position
- Command history position
- Panel visibility states
- Panel sizes/positions
- Focus state

### WebSocket Integration

```typescript
interface ServerMessage {
  type: "game_output" | "game_state" | "event";
  content: string;
  state?: {
    current_room_id: string;
    inventory: Item[];
    health: number;
    // ...
  };
}
```

**Do NOT parse game text to derive state.** Request structured updates from the server.

---

## 5. Database Schema

### Initial Tables (PostgreSQL)

```sql
-- Players
CREATE TABLE players (
  id UUID PRIMARY KEY,
  username VARCHAR UNIQUE NOT NULL,
  password_hash VARCHAR NOT NULL,
  current_room_id UUID NOT NULL,
  health INT DEFAULT 100,
  max_health INT DEFAULT 100,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW(),
  FOREIGN KEY (current_room_id) REFERENCES rooms(id)
);

-- Rooms
CREATE TABLE rooms (
  id UUID PRIMARY KEY,
  name VARCHAR NOT NULL,
  description TEXT NOT NULL,
  region_id UUID,
  created_at TIMESTAMP DEFAULT NOW(),
  FOREIGN KEY (region_id) REFERENCES regions(id)
);

-- Exits
CREATE TABLE exits (
  id UUID PRIMARY KEY,
  from_room_id UUID NOT NULL,
  to_room_id UUID NOT NULL,
  direction VARCHAR NOT NULL,
  locked BOOLEAN DEFAULT FALSE,
  hidden BOOLEAN DEFAULT FALSE,
  FOREIGN KEY (from_room_id) REFERENCES rooms(id),
  FOREIGN KEY (to_room_id) REFERENCES rooms(id),
  UNIQUE (from_room_id, direction)
);

-- Items
CREATE TABLE items (
  id UUID PRIMARY KEY,
  name VARCHAR NOT NULL,
  description TEXT,
  item_type VARCHAR NOT NULL,
  owner_id UUID,
  location_room_id UUID,
  location_container_id UUID,
  can_take BOOLEAN DEFAULT TRUE,
  FOREIGN KEY (owner_id) REFERENCES players(id),
  FOREIGN KEY (location_room_id) REFERENCES rooms(id),
  FOREIGN KEY (location_container_id) REFERENCES items(id)
);

-- Inventory
CREATE TABLE inventory (
  id UUID PRIMARY KEY,
  player_id UUID NOT NULL,
  item_id UUID NOT NULL,
  slot INT,
  FOREIGN KEY (player_id) REFERENCES players(id),
  FOREIGN KEY (item_id) REFERENCES items(id),
  UNIQUE (player_id, item_id)
);

-- Regions (for organization, optional in M1)
CREATE TABLE regions (
  id UUID PRIMARY KEY,
  name VARCHAR NOT NULL,
  description TEXT
);
```

---

## 6. Test Architecture

### Unit Test Pattern (pytest)

```python
# tests/test_commands/test_movement.py
import pytest
from app.commands.parser import parse_command
from app.engine.executor import execute_command
from app.domain.player import Player
from app.domain.room import Room

@pytest.fixture
def seeded_world(db_session):
    """Provides a deterministic 5-room world."""
    # Create rooms, exits, items, players
    yield world_setup

def test_player_can_move_north(seeded_world, db_session):
    # Arrange
    player = seeded_world.players["alan"]
    command = parse_command("north")
    
    # Act
    result = execute_command(command, player, db_session)
    
    # Assert
    assert result.success
    assert result.new_room_id == seeded_world.rooms["forest"].id
    assert player.current_room_id == seeded_world.rooms["forest"].id
```

### Integration Test Pattern

```python
# tests/integration/test_websocket.py
@pytest.mark.asyncio
async def test_player_connects_and_receives_room_description():
    async with connect_to_websocket("ws://localhost:8000/ws") as ws:
        msg = await ws.recv()
        assert "Town Square" in msg
```

### Playwright Pattern

```typescript
// e2e/tests/movement.spec.ts
import { test, expect } from '@playwright/test';

test('player can move north from town square to forest', async ({ page }) => {
  await page.goto('http://localhost:5173');
  
  // Login
  await page.fill('[data-testid="username"]', 'alan');
  await page.fill('[data-testid="password"]', 'password');
  await page.click('[data-testid="login-button"]');
  
  // Check initial room
  await expect(page.locator('[data-testid="room-name"]')).toContainText('Town Square');
  
  // Move north
  await page.fill('[data-testid="command-input"]', 'north');
  await page.keyboard.press('Enter');
  
  // Verify new room
  await expect(page.locator('[data-testid="room-name"]')).toContainText('Forest');
  await expect(page.locator('[data-testid="transcript"]')).toContainText('You walk north');
});
```

---

## 7. Deployment Test Gate

### scripts/test.sh

```bash
#!/bin/bash
set -e

echo "🔨 Building test containers..."
docker compose -f compose.test.yaml build

echo "🧪 Running backend unit tests..."
docker compose -f compose.test.yaml run --rm backend_test
BACKEND_EXIT=$?

echo "🧪 Running frontend unit tests..."
docker compose -f compose.test.yaml run --rm frontend npm run test
FRONTEND_EXIT=$?

# STOP if unit tests fail
if [ $BACKEND_EXIT -ne 0 ] || [ $FRONTEND_EXIT -ne 0 ]; then
  echo "❌ Unit tests FAILED. Deployment blocked."
  exit 1
fi

echo "✅ All unit tests passed!"
```

### scripts/deploy.sh

```bash
#!/bin/bash
set -e

echo "🔍 Validating environment..."
if [ ! -f .env ]; then
  cp .env.example .env
fi

echo "📦 Running test gate..."
./scripts/test.sh
if [ $? -ne 0 ]; then
  echo "❌ Test gate failed. Deployment stopped."
  exit 1
fi

echo "🐳 Building Docker images..."
docker compose build

echo "🚀 Starting application stack..."
docker compose up -d

echo "⏳ Waiting for health checks..."
sleep 5
docker compose ps

echo "✅ Deployment complete!"
echo "   Backend:  http://localhost:8000"
echo "   Frontend: http://localhost:5173"
echo "   Postgres: localhost:5432"
```

### Makefile

```makefile
.PHONY: test e2e deploy dev down clean

dev:
	docker compose up

down:
	docker compose down

test:
	./scripts/test.sh

e2e:
	./scripts/e2e.sh

deploy:
	./scripts/deploy.sh

clean:
	docker compose -f compose.test.yaml down -v
	docker system prune -f

logs:
	docker compose logs -f backend
```

---

## 8. Initial Seed World

### 5-Room World Map

```
          Forest
         (north)
             |
             |
Blacksmith--Town Square--Inn
 (west)     (center)    (east)
             |
          (south)
             |
           Docks
```

### Room Data

| Name | Description | Initial Items | NPCs |
|------|-------------|----------------|------|
| Town Square | Central gathering place | torch (can take) | - |
| Forest | Dense woods north of town | mushroom (can take) | - |
| Inn | Cozy lodging | key (can take) | - |
| Blacksmith | Forge and workshop | sword (can take) | - |
| Docks | Waterfront activity | barrel (cannot take) | - |

### Seed Script

```python
# scripts/seed_world.py
from app.domain.room import Room
from app.domain.item import Item
from app.domain.exit import Exit

def seed_world(db_session):
    """Create the 5-room deterministic world."""
    
    # Create rooms
    town_square = Room(
        id="town_square",
        name="Town Square",
        description="A bustling marketplace at the heart of the town..."
    )
    
    forest = Room(id="forest", name="Forest", description="...")
    inn = Room(id="inn", name="Inn", description="...")
    blacksmith = Room(id="blacksmith", name="Blacksmith", description="...")
    docks = Room(id="docks", name="Docks", description="...")
    
    # Create exits
    exits = [
        Exit(from_room="town_square", to_room="forest", direction="north"),
        Exit(from_room="town_square", to_room="inn", direction="east"),
        Exit(from_room="town_square", to_room="blacksmith", direction="west"),
        Exit(from_room="town_square", to_room="docks", direction="south"),
        # Reverse exits
        ...
    ]
    
    # Create items
    torch = Item(
        id="torch_1",
        name="torch",
        description="A flickering torch",
        location_room="town_square",
        can_take=True
    )
    
    # Persist all
    db_session.add_all([town_square, forest, inn, blacksmith, docks] + exits + [torch, ...])
    db_session.commit()
```

---

## 9. First Incremental Implementation Steps

### Phase 1: Skeleton (Week 1, Days 1-2)
- [ ] Project structure created
- [ ] Docker Compose files (dev + test)
- [ ] FastAPI app with /health endpoint
- [ ] React app with placeholder Terminal component
- [ ] Database connection, Alembic setup
- [ ] GitHub Actions or local CI script ready
- [ ] README.md with setup instructions

### Phase 2: Foundation (Week 1, Days 3-5)
- [ ] SQLAlchemy models for Player, Room, Item, Exit
- [ ] Alembic migration for initial schema
- [ ] Seed script creates 5-room world
- [ ] Database tests pass
- [ ] Unit tests for domain entities

### Phase 3: Command Parsing (Week 2, Days 1-2)
- [ ] Command parser for: north, south, east, west, up, down, look, inventory, help
- [ ] Command model (Pydantic)
- [ ] Unit tests for parser

### Phase 4: Game Engine (Week 2, Days 3-4)
- [ ] Game engine with validator + executor
- [ ] Implement LOOK command
- [ ] Implement MOVE commands (north, south, etc.)
- [ ] Implement INVENTORY command
- [ ] Result models (structured game outcomes)
- [ ] Unit tests for each command

### Phase 5: Narration (Week 2, Day 5)
- [ ] Narration service converts results to prose
- [ ] Game service orchestrates engine + narration
- [ ] Unit tests for narration

### Phase 6: WebSocket & API (Week 3, Days 1-2)
- [ ] WebSocket endpoint for /ws
- [ ] Player authentication (simple, no OAuth yet)
- [ ] WebSocket message handler
- [ ] Game state updates via WebSocket
- [ ] Integration tests for WebSocket

### Phase 7: Frontend (Week 3, Days 3-4)
- [ ] Terminal component structure
- [ ] WebSocket client (useWebSocket hook)
- [ ] Transcript rendering
- [ ] Command input with Enter handling
- [ ] Command history (↑ ↓ keys)
- [ ] Unit tests for Terminal component

### Phase 8: Item Interactions (Week 3, Day 5)
- [ ] GET / TAKE command
- [ ] DROP command
- [ ] EXAMINE command
- [ ] Item state persistence
- [ ] Unit tests

### Phase 9: Multiplayer Events (Week 3, Day 5+)
- [ ] Game events (PlayerEntered, PlayerLeft, ItemDropped, etc.)
- [ ] Event fan-out to WebSocket clients
- [ ] Player presence in rooms
- [ ] Integration tests for multiplayer

### Phase 10: Playwright Tests (Week 3, Final Days)
- [ ] Login test
- [ ] Movement test
- [ ] Inventory test
- [ ] Examine test
- [ ] Multiplayer test (two players in same room)

### Phase 11: Documentation & Deployment (Final)
- [ ] README.md complete
- [ ] CLAUDE.md with project instructions
- [ ] Deployment script tested
- [ ] Test gate enforced in CI

---

## 10. Deployment Pipeline

```
Local: ./scripts/deploy.sh
  ↓
1. Build test containers
2. Run backend unit tests     ← GATE
3. Run frontend unit tests    ← GATE
4. If PASS:
     Build production containers
     docker compose up
     Wait for health checks
     Report success
   If FAIL:
     Exit with code 1, block deployment
```

Later CI (GitHub Actions) will mirror this.

---

## 11. Definition of "Done" for M1

A feature is not done until:

- ✅ Code is implemented
- ✅ Unit tests exist and PASS
- ✅ Integration tests for shared state (multiplayer)
- ✅ Playwright E2E tests for user workflows
- ✅ Lint/type checks pass
- ✅ Database migrations created (Alembic)
- ✅ Docker build succeeds
- ✅ All tests pass before deployment gate
- ✅ Documentation updated (README, CLAUDE.md)
- ✅ Claude reports exactly what changed and what tests ran

**No feature is done until tests pass and deployment succeeds.**

---

## 12. Key Success Metrics for M1

By the end of Milestone One, this should be true:

1. ✅ A player can open a browser and connect
2. ✅ Player can navigate between 5 rooms using directional commands
3. ✅ Player can see room descriptions, exits, and items
4. ✅ Player can pick up and drop items
5. ✅ Player inventory persists across disconnect/reconnect
6. ✅ Multiple players can occupy the same room and see each other
7. ✅ All tests pass automatically before deployment
8. ✅ Deterministic seed data creates a reproducible world
9. ✅ No AI is used (FakeAIProvider only)
10. ✅ Architecture is ready for Milestone Two (AI command interpretation)

---

## 13. Scalability Plan for 1,000 Connected Players

This is post-Milestone-One work. The current single-process presence registry,
direct WebSocket delivery, and global in-process command lock are appropriate
for development but are not a production design for 1,000 concurrent players.
PostgreSQL remains the authoritative store; Redis holds only ephemeral presence,
routing, queueing, and rate-limit state.

### Known Performance Risks

- The global command lock serializes otherwise independent player actions.
- Presence and connection ownership exist only inside one backend process.
- Room-event delivery scans all connected players instead of indexed room members.
- Slow WebSocket clients can delay command handling because delivery is inline.
- Private and room messages cannot cross backend instances.
- An unfiltered `who` response could produce an excessively large transcript.
- Connection spikes, reconnect storms, and popular rooms can create hot spots.
- Database and WebSocket pool limits have not been validated under sustained load.

### Required Scalability Work

- [ ] Replace the global command lock with PostgreSQL transactions and consistently
      ordered row-level locks for contested players and items.
- [ ] Store online-session leases and room membership indexes in Redis, with expiry
      and disconnect cleanup for abandoned sessions.
- [ ] Route room and private events across backend instances with Redis Pub/Sub or
      Streams while preserving PostgreSQL as the source of authoritative state.
- [ ] Use bounded per-connection outgoing queues so slow clients cannot block the
      command path; define overflow and disconnect behavior.
- [ ] Address room events through Redis room-membership sets instead of scanning
      every connected player.
- [ ] Add a paginated and filtered `who` command rather than returning all players.
- [ ] Add per-player and per-room command/message rate limits.
- [ ] Configure and measure database, Redis, and WebSocket connection pool limits.
- [ ] Add metrics for active connections, commands per second, event fan-out,
      queue depth, dropped messages, errors, and latency percentiles.
- [ ] Add graceful connection draining for backend deploys and restarts.

### Load-Test Gate

Before claiming support for 1,000 players, define the expected command rate and
room-size distribution, then test at least these scenarios:

1. 1,000 mostly idle WebSocket connections with heartbeats.
2. Sustained movement and chat across many rooms.
3. A crowded-room fan-out test with hundreds of occupants.
4. Concurrent attempts to take or give the same item.
5. Disconnect and reconnect storms.
6. Multiple backend instances with cross-instance `say`, `tell`, and movement.

Record p50, p95, and p99 command latency, message-delivery latency, error rate,
resource usage, and database lock contention. Concrete pass thresholds must be
agreed before the load test; “1,000 connected” alone is not a sufficient capacity
definition because idle connections and simultaneous commands have very different
costs.

### Deferred Room-Capacity Policy

Prefer keeping popular rooms socially unified rather than immediately splitting
them into separate instances. Introduce two operational thresholds when load
testing shows they are needed:

- A soft threshold, initially suggested at 100 occupants, where low-value activity
  events are summarized, repetitive arrivals and departures are batched, and room
  chat receives stricter rate limits.
- An emergency hard cap, initially suggested at 500 occupants, where additional
  entry is rejected with a clear explanation and available neighboring rooms are
  suggested.

The numbers are starting points, not promises; select them from measured fan-out,
latency, and client-rendering results. If a hard cap is active, room entry must be
atomic under concurrent movement. A rejected move leaves the player in the source
room, consumes no torch fuel, and emits no departure or arrival event.

Before implementation, define explicit policies for reconnecting players, staff,
and parties. Private `tell` messages may continue across rooms, while `say` remains
room-scoped. Overflow room instances are a last resort because they split players,
conversation, and authoritative shared-item state; use them only as an intentional
game design with clearly defined instance ownership and item behavior.

## Next Steps

1. **Create the directory structure** (backend/, frontend/, e2e/, etc.)
2. **Write docker/compose.yaml and compose.test.yaml**
3. **Set up FastAPI project** with pyproject.toml
4. **Set up React + Vite project** with package.json
5. **Initialize Alembic** for database migrations
6. **Create pytest conftest.py** with fixtures
7. **Implement Phase 1-2** (skeleton + foundation)
8. **Build incrementally, testing as you go**

---

## Questions for the User

Before we start implementing:

1. **Authentication complexity:** Do you want a full user account system with password hashing, or a simple session-based login for testing?
2. **AI provider for later:** Are you aiming for Anthropic Claude or OpenAI initially, or flexible for both?
3. **Frontend styling:** Prefer a minimal terminal-style aesthetic or more polished UI?
4. **Database:** Ready to run PostgreSQL in Docker, or prefer SQLite for early development?
5. **Development pace:** Full-time development, or part-time with breaks?

Ready to begin?
