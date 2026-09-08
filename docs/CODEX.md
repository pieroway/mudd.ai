# CODEX.md — AI-Enhanced MUD Project Instructions

This file contains project-specific instructions for Codex working on this repository.

## Quick Context

**Project:** AI-Enhanced MUD (Milestone Four — one AI-powered NPC)

**Current Status:** M1, M2, M3, and the first UI milestone are complete. Real AI remains development-only; optional narration is disabled by default.

**Architecture:** 7-layer deterministic game engine with controlled AI abstraction

**Key Principle:** THE GAME ENGINE OWNS REALITY

See [AI_MUD_CODEX_PROJECT_PROMPT.md](AI_MUD_CODEX_PROJECT_PROMPT.md) for complete specification.

---

## Before You Start

1. Review [AGENTS.md](AGENTS.md) — defines how to work on this project
2. Review [MILESTONE_TWO_PLAN.md](../MILESTONE_TWO_PLAN.md) for completed scope and validation, and [docs/ROADMAP.md](ROADMAP.md) for future work.
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

### Milestone One: Complete
- Persistent five-room world, SQLAlchemy models, Alembic migrations, and seed data
- Classic command parser, authoritative engine, movement, and item interactions
- React terminal, WebSocket integration, and multiplayer events
- Docker environments, automated tests, and deployment quality gate

### Milestone Two: Complete
- Strict AI command contract, validation, and deterministic FakeAIProvider
- Classic-parser-first routing with optional natural-language fallback
- Development-only OpenAI adapter with bounded usage and mocked HTTP tests
- Backend, WebSocket, and browser coverage; historical gate results in the M2 plan

### Additional Implemented Work and Remaining Boundaries
- Authenticated accounts, secure character ownership, and persistent daily AI allowances
- Daily AI units default to 50. Admins grant persistent bonus credits with
  `/ai credits add <username> [units]` (default 50), including self-grants;
  see [AI usage](AI_USAGE.md) for accounting and validation.
- Operator-assigned admin roles; admin-only `/ai narration on|off`, saved per account
  and off by default. Help includes admin-only commands only for current admins.
- Public live-AI access still requires shared spending controls and public-launch security review
- Optional narration is implemented; see [M3](../MILESTONE_THREE_PLAN.md) for verification status
- M4 adds Edric's private conversations and persistent per-character memory; see
  [the M4 plan](../MILESTONE_FOUR_PLAN.md) for scope and verification status.
- World generation and further UI extensions remain future work

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
| [MILESTONE_ONE_PLAN.md](../MILESTONE_ONE_PLAN.md) | M1 roadmap with phases, schema, patterns |
| [MILESTONE_TWO_PLAN.md](../MILESTONE_TWO_PLAN.md) | Completed M2 scope and validation record |
| [MILESTONE_UI_PLAN.md](../MILESTONE_UI_PLAN.md) | UI milestone, acceptance criteria, and validation record |
| [docs/ROADMAP.md](ROADMAP.md) | Future gameplay and deferred features |
| [CODEX.md](CODEX.md) | This file — project-specific instructions |
| [README.md](../README.md) | Developer setup guide |
| [compose.yaml](../compose.yaml) | Development Docker stack |
| [compose.test.yaml](../compose.test.yaml) | Test Docker stack (isolated) |
| [backend/pyproject.toml](../backend/pyproject.toml) | Backend dependencies |
| [frontend/package.json](../frontend/package.json) | Frontend dependencies |

---

## Architecture Refresh

### Current Command Flow

```
Browser
    ↓ WebSocket
FastAPI (main.py)
    ↓
Authenticated API / WebSocket routes
    ↓
Game service: classic parser first; optional AI fallback with strict validation
    ↓
Authoritative game engine
    ↓
Repository / SQLAlchemy persistence
    ↓
PostgreSQL
```

AI interpretation proposes commands before engine execution. Optional AI narration
describes committed outcomes after authoritative results and multiplayer events
are delivered; its prose is never used to update game state.
PostgreSQL owns persistent game state; Redis is reserved for ephemeral concerns.

---

## Testing Strategy

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

### Authenticated Character Ownership
- Password-based accounts and authenticated sessions replace M1 username-only access
- Each account owns one character initially
- See [docs/AUTHENTICATION.md](AUTHENTICATION.md) for session and migration behavior

### FakeAIProvider
- Gameplay tests use FakeAIProvider; provider adapter tests use mocked HTTP
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
→ Check [README.md#Troubleshooting](../README.md#troubleshooting)

### "I don't understand the architecture"
→ Review [MILESTONE_ONE_PLAN.md](../MILESTONE_ONE_PLAN.md) section 1-3, then ask for clarification

### "Should I add X feature?"
→ Check the completed milestone plans and [docs/ROADMAP.md](ROADMAP.md), then agree on a small increment within the user's requested scope.

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

## Next Work

M1, M2, and the first [UI milestone](../MILESTONE_UI_PLAN.md) are complete.
The UI increment passed the full deployment gate on September 6, 2026 and is
deployed to the local development stack. Validation results are recorded in its plan.
Use [docs/ROADMAP.md](ROADMAP.md) and the
[UI inspiration brief](mud_ai_ui_inspiration.md) to scope the next requested increment.
The [M3 narration milestone](../MILESTONE_THREE_PLAN.md) passed its full deployment
gate September 6, 2026. [M4](../MILESTONE_FOUR_PLAN.md) implements one AI-powered NPC;
its plan records current verification status. M5 is controlled world generation.
Public live-AI enablement still
requires shared spending controls and a renewed security review.

For each increment, define behavior, add appropriate tests, implement targeted
changes, and run the required checks before deployment. Historical validation
records do not substitute for testing new changes.

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
3. [MILESTONE_ONE_PLAN.md](../MILESTONE_ONE_PLAN.md)
4. [AI_MUD_CODEX_PROJECT_PROMPT.md](AI_MUD_CODEX_PROJECT_PROMPT.md) (complete truth)
