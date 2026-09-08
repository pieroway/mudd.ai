# Milestone Three — Optional AI Narration

## Status

Complete — full deployment gate passed September 6, 2026 (America/Toronto),
and the local development stack is deployed. The project owner confirmed
`/ai narration on|off` is working on September 7, 2026. This is manual behavior
confirmation; no new full deployment-gate result is recorded here.
Poetic narration style improvements are deferred for a later pass.
M4 remains one AI-powered NPC.

## Delivered behavior

- `AI_NARRATION_ENABLED=false` is the default and is independent of command
  interpretation. It controls server availability; enable it explicitly in the
  local `.env` and recreate the backend. Each account must separately opt in.
- `/ai narration on|off` saves the authenticated caller's preference in PostgreSQL.
  Every account, including admins, starts with narration off. The entire `/ai`
  command namespace is admin-only and bypasses AI interpretation. Invalid syntax,
  missing permission, or a server-disabled `on` request cannot change the preference.
  Toggling costs no AI allowance. Preferences survive reload and sign-in.
- Help includes admin-only commands only for current admins. Roles are assigned
  only by the local operator tool; registration cannot grant admin access.
  Revocation resets narration off. Permissions and preferences are checked before
  provider calls and again before returning generated prose.
- The engine completes and commits each action first. The client receives its
  normal result and authoritative snapshot; multiplayer recipients receive their
  normal events before any narration call.
- The narrator receives a frozen, bounded structured outcome containing only
  `action`, `success`, and `authoritative_text`. This is captured from the engine
  result before player-presence text is appended. No database objects, identity,
  session tokens, chat, history, full inventory snapshot, or world map are supplied.
- Narration supports look, move, take, drop, examine, open, close, use, extinguish,
  look_in, take_from, and put, including failed engine outcomes. Help, inventory,
  who, speech, giving items to another player, and interpretation errors are excluded.
- A separate authenticated `narration` WebSocket message carries optional `text`
  and updated `ai_usage`. The transcript labels it `[AI narration]` and renders
  plain text. It cannot update inventory, room state, success, or event routing.
- Invalid/empty/oversized responses, refusals, timeouts, provider exceptions,
  unavailable allowance, and reservation failures silently retain the normal result.
  A null narration text refreshes usage without adding a transcript line.
- Session authorization is checked before the provider call and after completion,
  and again when sending the message. Narration holds no game lock or transaction.

## Providers and limits

FakeAIProvider provides deterministic examples such as `You gather up the torch.`
and otherwise repeats the authoritative text. Automated tests use this provider
or mocked HTTP; no paid API calls are required or made by tests.

The existing development-only OpenAI adapter supports narration through the same
Responses API transport. It requests a strict text-only schema, `store=false`,
no tools, and no conversation history. The prompt prohibits invented facts or
additional player actions. Schema validation does not establish semantic truth:
generated prose can still be inaccurate, so the normal engine result stays visible
and remains authoritative. Live narration quality has not been evaluated.

API contract reference: [OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs).

Interpretation and narration share one provider instance and its existing
`AI_COMMAND_*` limits: five-second deadline, 4,096 input bytes, 512 output tokens,
two concurrent calls, and 100 lifetime requests by default. Narration input size
includes the serialized outcome. Oversized outcomes fall back without truncation.
Responses are limited to 64 KiB, with narration text limited to 2,000 characters.
No automatic retry is performed. Real AI remains restricted to development.

Each narration attempt also consumes one persistent daily account request. A
natural-language action may use two requests: interpretation and narration.
Classic command execution remains free; optional narration after it uses allowance.
Failed attempts count. Exhaustion never prevents a classic engine action.

With a real provider enabled, engine-visible room/item descriptions and failure
text are sent externally; failure text may include a player-supplied target.
Do not enter secrets. `store=false` is not a zero-retention guarantee.

## Deliberate limits

The first implementation processes one command at a time per WebSocket, so the
next queued command from that player waits up to the narration deadline. Other
players can continue executing commands. Narration may appear among other players'
activity lines; it describes the triggering outcome, not a new current-state snapshot.
There is no background task queue, streaming, or persisted prose.
Migration `0008` adds `is_admin` and `ai_narration_enabled` to accounts, both false
for existing and new accounts. No new dependency is required.

## Verification

- Tests cover state isolation even when prose invents rewards, failure fallback,
  malformed responses, timeout, concurrent gameplay, shared allowance, authorization,
  privacy, transport order, plain-text rendering, and ignored narration state fields.
- Playwright runs with fake narration enabled and checks narration, allowance,
  admin opt-in and opt-out, persisted preference, non-admin denial, role-specific
  help, authoritative room state, and the existing inventory and mobile workflows.
  Its operator fixture creates an admin only in the isolated E2E database.
- Initial `scripts\test.bat`: exit 0, with 206 backend tests, 18 frontend tests,
  lint, type checks, and frontend build passing.
- Full `scripts\deploy.bat`: exit 0 on September 6, 2026 (America/Toronto;
  September 7 UTC). All 206 backend tests passed with 91% coverage; Ruff and mypy
  passed (39 source files). Frontend lint, type checks, 18 tests, and build passed.
- Production-like Compose validation, production images, and development images
  built successfully. All 6 Playwright workflows passed in 37.5 seconds with fake
  narration enabled, including inventory synchronization and mobile layout.
- The 10-user, 30-second smoke test passed with 0 failures among 273 measured
  command responses and command latency p95 of 706 ms. Authoritative-state
  invariants passed. Smoke testing used narration disabled; it does not measure
  real-provider latency or narration throughput.
- The local backend, frontend, PostgreSQL, and Redis passed health checks.
  No live AI requests were made during verification. Two existing backend
  dependency deprecation warnings remain. Production-like validation covered
  configuration and builds; no public deployment was performed.
