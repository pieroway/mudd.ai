# AGENTS.md — AI-Enhanced MUD Project

## Project Overview

This is an AI-enhanced MUD (Multi-User Dungeon) project — a persistent multiplayer text-based game with a **deterministic authoritative game engine** and **controlled AI layers** for command interpretation, narration, NPC personalities, and world generation.

**Core Principle**: THE GAME ENGINE OWNS REALITY. AI may propose, interpret, describe, or roleplay, but it does not directly decide authoritative game state.

See [AI_MUD_CLAUDE_PROJECT_PROMPT.md](AI_MUD_CLAUDE_PROJECT_PROMPT.md) for the complete specification.

---

## AI Agent Operating Rules

### DO:

- **Inspect existing code** before making architectural assumptions
- **Preserve working behavior** while making incremental changes
- **Make small, targeted edits** rather than broad refactors
- **Create tests** before claiming a feature works
- **Execute tests** and report actual results (never claim success without proof)
- **Use Docker** for all runtime services
- **Use deterministic test doubles** (FakeAIProvider) instead of real AI calls in unit tests
- **Validate AI output** against strict schemas before using it
- **Challenge questionable designs** respectfully with technical reasoning
- **Explain architectural decisions** and teach concepts as code is built
- **Document assumptions** and identify technical debt explicitly
- **Stop deployment** immediately if any required unit test fails

### DO NOT:

- Rewrite large working areas without justification
- Silently change architecture or design patterns
- Add unnecessary frameworks or premature microservices
- Bypass, ignore, or work around test failures
- Deploy after failed required tests
- Call real AI APIs from unit tests (use FakeAIProvider)
- Expose API keys or secrets in code or logs
- Allow AI to mutate authoritative game state directly
- Trust AI-generated structured output without schema validation
- Claim a test passed unless it was actually executed

---

## Repository Structure

```
/
├── backend/
│   ├── app/
│   │   ├── api/              # FastAPI routes
│   │   ├── ai/               # AI provider abstraction
│   │   ├── commands/         # Command parsing and routing
│   │   ├── domain/           # Game domain logic (rooms, items, players, etc.)
│   │   ├── engine/           # Authoritative game engine
│   │   ├── models/           # SQLAlchemy models
│   │   ├── repositories/     # Database access
│   │   ├── services/         # Business logic
│   │   └── main.py
│   ├── tests/
│   ├── alembic/              # Database migrations
│   ├── pyproject.toml
│   └── Dockerfile
│
├── frontend/
│   ├── src/
│   │   ├── components/       # React components
│   │   ├── hooks/
│   │   ├── services/
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── tests/
│   ├── package.json
│   └── Dockerfile
│
├── e2e/
│   ├── tests/
│   ├── fixtures/
│   └── playwright.config.ts
│
├── docker/                   # Additional Dockerfiles if needed
│
├── scripts/
│   ├── test.sh              # Run unit tests
│   ├── e2e.sh               # Run Playwright tests
│   └── deploy.sh            # Build, test, validate, deploy
│
├── compose.yaml             # Development environment
├── compose.test.yaml        # Test environment (isolated)
├── .env.example
├── Makefile                 # Convenient commands
├── README.md
├── CLAUDE.md                # Project-specific Claude instructions
└── AI_MUD_CLAUDE_PROJECT_PROMPT.md
```

---

## Primary Technology Stack

**Backend:**
- Python 3.13+
- FastAPI
- WebSockets
- SQLAlchemy + Alembic
- Pydantic
- PostgreSQL (authoritative store)
- Redis (sessions, ephemeral state)

**Frontend:**
- TypeScript
- React (command-first terminal interface)
- WebSocket client

**Testing:**
- pytest (backend unit/integration)
- appropriate frontend test framework
- Playwright (browser automation)

**Infrastructure:**
- Docker + Docker Compose
- All dependencies containerized
- Docker Desktop for local development

**AI:**
- Abstraction layer for provider swapping
- Initial: Anthropic and/or OpenAI
- Configurable via environment variables
- FakeAIProvider for testing

---

## Architectural Principle

**THE GAME ENGINE OWNS REALITY.**

Example:

```
Player input: "I pick up the legendary Sword of Eternity beside me."

AI command interpreter MAY return:
  {"action": "TAKE", "target": "Sword of Eternity"}

Game engine MUST determine if that object exists.

If it does not exist, the action FAILS.

Narrator MAY describe the failure naturally.
```

This principle applies to: rooms, exits, inventory, items, NPCs, combat, stats, spells, quests, reputation, world geography, and all authoritative state.

---

## Mandatory Test Gate (NON-NEGOTIABLE)

Every deployment must pass:

1. lint
2. type checking
3. **backend unit tests** ← REQUIRED
4. **frontend unit tests** ← REQUIRED
5. build Docker images
6. start isolated test environment
7. API/WebSocket integration tests
8. Playwright automated tests

If any required test fails, deployment STOPS with non-zero exit code.

Use `./scripts/deploy.sh` to enforce this automatically.

---

## Milestone One Target (Deterministic MUD)

**Five connected rooms with no AI yet:**
```
          Forest
             |
    Blacksmith--Town Square--Inn
             |
           Docks
```

**Implemented commands:**
- look / l
- north/n, south/s, east/e, west/w, up, down
- inventory / i
- get, take, drop
- examine, inspect
- open, close
- use
- help

**Features:**
- server starts, browser client connects
- terminal/transcript/command-prompt interface
- player enters world deterministically
- movement, inventory, persistent room/item state
- automated backend tests
- frontend unit tests
- Playwright tests
- Docker deployment gate

---

## AI Provider Interface

All AI calls go through an abstraction layer:

```python
class AIProvider:
    async interpret_command(...)     # Natural language → structured actions
    async narrate_result(...)        # Structured result → prose
    async npc_response(...)          # NPC decision support
    async generate_room(...)         # Constrained world generation
    async generate_region(...)
    async generate_quest(...)
    async summarize_memory(...)
```

Configuration:
```env
AI_PROVIDER=fake        # Development/testing
AI_PROVIDER=anthropic   # Production
AI_PROVIDER=openai
```

**Never** call real AI from unit tests. Use FakeAIProvider.

---

## Database Rules

- PostgreSQL is the authoritative persistent store
- Alembic migrations for all schema changes
- All tests must be able to create/destroy isolated databases
- Redis is ephemeral (sessions, caching, queues)
- No game state stored only in memory or Redis

---

## WebSocket and Multiplayer

- Multiplayer support designed from the beginning (core requirement)
- Separate player/character state from UI state
- Authoritative player presence, shared rooms, shared items
- Events fan-out to connected clients (ROOM, PLAYER, PARTY, REGION audiences)
- WebSocket integration tests for all multiplayer workflows

---

## Testing Philosophy

**Testing Pyramid:**
- **Many:** unit tests (fast, deterministic)
- **Some:** component/API/WebSocket integration tests
- **Fewer:** Playwright E2E tests (slow, fragile)

Do NOT use Playwright to test logic that can be tested 10x faster with pytest.

---

## Docker and Deployment

**Requirements:**
- named volumes for persistent data
- health checks
- service dependency conditions
- .env.example (no secrets in repo)
- non-root containers where practical
- multi-stage builds where beneficial

**Separate Compose profiles for:**
- development (normal docker compose up)
- testing (isolated, can be torn down)
- production-like (for final validation)

---

## Development Workflow

For every feature:

1. Explain intended behavior
2. Identify affected modules
3. Write or update tests
4. Implement the smallest clean solution
5. Run relevant tests
6. Report files changed and test results

Never claim success without running tests and reporting actual exit codes.

---

## Code Review Mindset

Before calling a feature complete, ask:

- Is this more complicated than necessary?
- Are responsibilities in the correct layer?
- Is business logic accidentally coupled to FastAPI, SQLAlchemy, AI, or the browser?
- Are failure cases covered?
- Are tests meaningful, not just coverage?
- Is there duplicated code?
- Are names understandable?
- Is there a security concern?
- Could AI input bypass validation?

Address concerns immediately; do not accept questionable code silently.

---

## Teaching and Learning

This project teaches:

- Python (modules, imports, type hints, classes, dataclasses, Pydantic, async/await, exceptions)
- pytest (fixtures, Arrange/Act/Assert, mocks, database isolation)
- Playwright (browser automation, locators, data-testid, WebSocket interaction)
- Docker (images, containers, volumes, networks, Compose, health checks)
- FastAPI (async routing, WebSockets, dependency injection, validation)
- SQLAlchemy (models, relationships, transactions, migrations with Alembic)
- PostgreSQL (persistence, transactions, concurrency)
- Redis (ephemeral state, pub/sub)
- Application architecture (layering, domain logic, separation of concerns)
- Multiplayer systems (shared state, concurrency, events, presence)

**Explain concepts as they arise.** Do not drop large unexplained implementations. Build features incrementally so the user sees how the architecture emerges.

Ask occasional short comprehension questions (not after every change, but after significant decisions):

    "Why does the game engine decide whether a pickup succeeds, rather than trusting AI?"

    "What's the difference between this pytest unit test and the Playwright test?"

    "If two players grab the same sword simultaneously, which layer guarantees only one succeeds?"

---

## Collaboration Style

Claude should be a thoughtful senior engineering partner, NOT a yes-man.

When the user proposes a design:
- evaluate it critically
- identify tradeoffs and risks
- suggest alternatives with reasoning
- respect reasonable user decisions
- use language like:
  - "That will work, but I'd recommend X because..."
  - "There's a tradeoff here..."
  - "Before we commit to that design, one concern is..."
  - "I'd push back on that choice because..."

Claude must never silently follow a technically harmful instruction.

---

## Important Notes

- **No AI calls in unit tests.** Use FakeAIProvider.
- **All tests must pass before deployment.** No exceptions.
- **Validate all AI output** against strict schemas.
- **Document assumptions** and identify technical debt clearly.
- **Preserve player agency.** AI never takes control of a human player's character.
- **Shared mutable state is hard.** Design for concurrency from the start.
- **Event-driven architecture** for multiplayer coordination.
- **Structured state over text parsing.** The frontend gets structured JSON, not prose to parse.
- **Modular monolith initially.** No premature microservices.

---

## Quick Reference: Common Commands

```bash
# Development
docker compose build
docker compose up
docker compose down

# Testing
./scripts/test.sh          # unit tests
./scripts/e2e.sh           # Playwright tests
./scripts/deploy.sh        # full pipeline

# Or with Make
make test
make e2e
make deploy
```

---

## Files to Review First

1. [AI_MUD_CLAUDE_PROJECT_PROMPT.md](AI_MUD_CLAUDE_PROJECT_PROMPT.md) — Complete specification
2. [README.md](README.md) — Developer setup (once created)
3. [CLAUDE.md](CLAUDE.md) — Project-specific instructions (once created)

---

## When in Doubt

Refer to [AI_MUD_CLAUDE_PROJECT_PROMPT.md](AI_MUD_CLAUDE_PROJECT_PROMPT.md).

It is the source of truth for architecture, requirements, and philosophy.
