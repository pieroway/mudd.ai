# CODEX.md — AI-Enhanced MUD Project Instructions

This file contains project-specific instructions for Codex working on this repository.

## Quick Context

**Project:** AI-Enhanced MUD (Milestone Two — AI command interpretation)

**Current Status:** Milestone One complete; Milestone Two security preparation and provider-contract work in progress

**Architecture:** 7-layer deterministic game engine with controlled AI abstraction

**Key Principle:** THE GAME ENGINE OWNS REALITY

See [AI_MUD_CODEX_PROJECT_PROMPT.md](AI_MUD_CODEX_PROJECT_PROMPT.md) for complete specification.

---

## Before You Start

1. Review [AGENTS.md](AGENTS.md) — defines how to work on this project
2. Review [MILESTONE_ONE_PLAN.md](MILESTONE_ONE_PLAN.md) — M1 implementation roadmap
3. Read the relevant section of [AI_MUD_CODEX_PROJECT_PROMPT.md](AI_MUD_CODEX_PROJECT_PROMPT.md)

---

## Development Rules

### DO:
- ✅ Test before claiming success
- ✅ Make small incremental changes
- ✅ Explain architectural decisions
- ✅ Preserve working code
- ✅ Use FakeAIProvider in tests (never real API calls)
- ✅ Document assumptions

### DO NOT:
- ❌ Deploy unless tests pass
- ❌ Rewrite large areas without justification
- ❌ Silently change architecture
- ❌ Claim success without running tests
- ❌ Let AI mutate game state directly

---

## Critical Constraints

1. **Test Gate (NON-NEGOTIABLE)**: All unit tests MUST pass before deployment
2. **Game Engine Authority**: Only the engine decides if actions succeed
3. **Deterministic Tests**: Use FakeAIProvider, no external API calls
4. **PostgreSQL Truth**: Game state lives in PostgreSQL, not memory or Redis
5. **Multiplayer Ready**: Architecture supports concurrent players from Day 1

---

## Current Project Status

### Phase 1: Complete ✅
- Directory structure created
- Docker Compose (dev + test) configured
- FastAPI skeleton with WebSocket endpoint
- React Terminal client skeleton
- pytest infrastructure
- Build/test/deploy scripts

### Phase 2: Next (Foundation)
- SQLAlchemy models (Player, Room, Item, Exit)
- Database migrations (Alembic)
- Seed script (5-room world)
- Unit tests for data layer

### Subsequent Phases
- Command parser
- Game engine (executor + validator)
- Narration service
- WebSocket integration
- Item system
- Multiplayer events
- Playwright E2E tests

---

## How to Work on Features

### Standard Workflow

```
1. Explain intended behavior
2. Identify affected modules
3. Write tests that describe expected behavior
4. Implement the smallest working solution
5. Run tests (must pass)
6. Report what changed and test results
```

### Testing Pattern

```python
# tests/test_commands/test_movement.py
def test_player_can_move_north(seeded_world):
    # Arrange
    player = seeded_world.players["alan"]
    
    # Act
    result = execute_command("north", player)
    
    # Assert
    assert result.success
    assert player.current_room == "forest"
```

### Never Skip Tests
If a test fails, STOP. Do not proceed until:
1. You understand why it failed
2. You've fixed the root cause
3. The test passes

---

## Key Files

| File | Purpose |
|------|---------|
| [AI_MUD_CODEX_PROJECT_PROMPT.md](AI_MUD_CODEX_PROJECT_PROMPT.md) | Complete specification (source of truth) |
| [AGENTS.md](AGENTS.md) | AI agent operating rules |
| [MILESTONE_ONE_PLAN.md](MILESTONE_ONE_PLAN.md) | M1 roadmap with phases, schema, patterns |
| [CODEX.md](CODEX.md) | This file — project-specific instructions |
| [README.md](README.md) | Developer setup guide |
| [compose.yaml](compose.yaml) | Development Docker stack |
| [compose.test.yaml](compose.test.yaml) | Test Docker stack (isolated) |
| [backend/pyproject.toml](backend/pyproject.toml) | Backend dependencies |
| [frontend/package.json](frontend/package.json) | Frontend dependencies |

---

## Architecture Refresh

### Current Layers (M1)

```
Browser
    ↓ WebSocket
FastAPI (main.py)
    ↓
API Routes (websocket.py, health.py)
    ↓
[Game Engine - TO BE BUILT]
    ↓
[Database Layer - TO BE BUILT]
    ↓
PostgreSQL
```

### Future Layers (Post-M1)

```
Browser
    ↓ WebSocket
FastAPI
    ↓
Command Parser (classic + AI)
    ↓
Game Engine (executor + validator)
    ↓
Narration Service
    ↓
AI Provider Abstraction
    ↓
PostgreSQL / Redis
```

---

## Testing Strategy for M1

### Unit Tests (Fast)
- Domain logic (rooms, players, items)
- Command parsing
- Validation rules
- Inventory mechanics
- Movement rules

### Integration Tests (Medium)
- Database operations
- WebSocket behavior
- API endpoints

### E2E Tests (Slow)
- Full player workflows (login → move → examine → etc)
- Multiplayer scenarios
- Persistence across reconnect

---

## Common Commands

```bash
# Development
make dev          # Start local stack
make down         # Stop services
make logs         # View backend logs

# Testing
make test         # Run unit tests (blocks on failure)
make e2e          # Run Playwright tests
make deploy       # Full pipeline (test → build → run)

# Cleanup
make clean        # Remove containers and volumes
```

---

## Debugging Tips

### Backend Logs
```bash
make logs
# Or in a separate terminal:
docker compose logs -f backend
```

### Database
```bash
psql -h localhost -U muduser -d muddb
# password: mudpass
```

### WebSocket Testing
```bash
wscat -c ws://localhost:8000/ws
```

### Frontend Console
Open http://localhost:5173 in browser → F12 → Console tab

---

## Important Decisions Made

### Username-Only Auth (M1)
- Simple: no passwords, no auth middleware yet
- Good enough for development and testing
- Security added in M2+

### FakeAIProvider
- All tests use FakeAIProvider (deterministic)
- No real API calls from unit tests
- Reduces costs and flakiness
- Allows offline development

### PostgreSQL in Docker
- No local setup required
- All developers get identical environment
- Matches production setup
- Data persists in named volume

### Modular Monolith (Not Microservices)
- Single backend process initially
- Separated by logical layers
- Split services only when justified
- Keeps development simple

---

## If You Get Stuck

### "Tests are failing"
→ Read the error carefully. What layer? What assumption?

### "Docker won't build"
→ Check [README.md#Troubleshooting](README.md#troubleshooting)

### "I don't understand the architecture"
→ Review [MILESTONE_ONE_PLAN.md](MILESTONE_ONE_PLAN.md) section 1-3, then ask for clarification

### "Should I add X feature?"
→ Check [MILESTONE_ONE_PLAN.md](MILESTONE_ONE_PLAN.md) for M1 scope. Out-of-scope → document as future work.

---

## Collaboration Style

I (Codex) will:
- ✅ Evaluate designs critically
- ✅ Challenge assumptions respectfully
- ✅ Explain concepts as they arise
- ✅ Ask comprehension questions occasionally
- ✅ Report test results before claiming success
- ✅ Identify technical debt explicitly

You will:
- ✅ Provide requirements and design direction
- ✅ Answer clarifying questions
- ✅ Review code and architecture choices
- ✅ Decide when to move to next phase

---

## Next Steps (After Phase 1)

1. **Phase 2 (Foundation)**: Database models + migrations
2. **Phase 3 (Parser)**: Command parsing
3. **Phase 4 (Engine)**: Command execution & validation
4. **Phase 5 (Narration)**: Convert results to prose
5. **Phase 6 (WebSocket)**: Real-time communication
6. **Continue through Phase 11**

Each phase:
- Starts with understanding
- Proceeds with tests
- Ends with passing tests + deployed code

---

## File — Future Additions

As the project grows, update this file:
- New architecture decisions
- New conventions
- Common debugging patterns
- Links to newly created documentation

---

## Questions?

Refer to the specification files in order:
1. [CODEX.md](CODEX.md) (this file)
2. [AGENTS.md](AGENTS.md)
3. [MILESTONE_ONE_PLAN.md](MILESTONE_ONE_PLAN.md)
4. [AI_MUD_CODEX_PROJECT_PROMPT.md](AI_MUD_CODEX_PROJECT_PROMPT.md) (complete truth)
