# Milestone Two Plan — AI Command Interpretation

## Status

**In progress — started September 2, 2026.**

The complete deployment gate passed on September 4, 2026 with 128 backend
tests, 10 frontend tests, 5 Playwright tests, a 10-user smoke load test with
zero command failures, and a passing authoritative-state invariant check.

Security work is tracked in
[`docs/SECURITY_REVIEW_2026-09-02.md`](docs/SECURITY_REVIEW_2026-09-02.md). Its
pre-M2 dependency, origin, input-limit, and logging findings should be addressed
before expanding the command surface or enabling a real AI provider.

Milestone One is complete. Milestone Two adds natural-language interpretation
without weakening the deterministic engine: AI may propose a structured command,
but the existing parser, validation, and engine remain authoritative.

## Scope

- Define a provider-independent `AIProvider` command-interpretation contract.
- Define a strict schema for proposed commands and reject invalid output.
- Add a deterministic `FakeAIProvider` for all automated tests.
- Preserve the classic parser as the first path for known commands.
- Send only otherwise-unrecognized input to the configured interpreter.
- Execute accepted proposals through the existing authoritative game engine.
- Add configuration that keeps AI disabled or fake by default.
- Add backend, WebSocket, frontend, and focused Playwright coverage.

Out of scope: AI narration, NPC intelligence, world generation, autonomous game
state changes, and real-provider calls from tests.

## Delivery Increments

### 1. Contract and validation

- [x] Add the provider interface and typed interpretation request/response models.
- [x] Define the allowed action vocabulary and per-action fields.
- [x] Add schema-validation and malformed-output tests.
- [x] Add `FakeAIProvider` with explicit deterministic fixtures.

### 2. Command fallback

- [x] Keep recognized classic commands on the existing zero-AI path.
- [x] Route unrecognized input to the provider through the game service.
- [x] Re-validate interpreted commands with normal engine rules.
- [x] Return a safe, useful error when interpretation fails or is unavailable.

### 3. Protocol and user experience

- [x] Expose whether a result used classic or AI-assisted interpretation in
      structured diagnostic metadata without requiring transcript parsing.
- [x] Add examples such as “walk toward the docks” and “look carefully at the
      torch.”
- [x] Document configuration, privacy boundaries, timeouts, and failure behavior.

### 4. Verification and optional real provider

- [x] Add WebSocket integration and Playwright coverage for natural language.
- [x] Verify AI proposals cannot bypass location, ownership, container, fuel, or
      multiplayer concurrency rules.
- [x] Run the complete deployment gate, including its smoke load test and state
      invariant check.
- [ ] Only then evaluate a real provider adapter behind explicit configuration.

## Definition of Done

- Familiar deterministic commands work without an AI call.
- Supported natural-language phrases become strictly validated commands.
- Invalid, unavailable, or malicious provider output cannot mutate game state.
- All automated tests use `FakeAIProvider`; no secrets or network calls are needed.
- The full deployment gate passes.

## Deferred Feature

The multi-user communications panel is recorded in `docs/ROADMAP.md`. It remains
post-M1 and is not required to complete AI command interpretation.
