# Milestone Four — One AI-Powered NPC

## Status

Implemented and deployed locally. The project owner confirmed Edric is working
on September 8, 2026. Edric is a stationary innkeeper in the Inn.
Poetic narration improvements remain a separate, deferred task.

## Player workflow

- Enter the Inn (`east` from Town Square), then use `talk edric <message>`.
  `look`, arrival text, and `help` explain the command.
- Conversations are private to the caller. Nearby players receive neither the
  player's message nor Edric's reply. `say` and `tell` retain their player-chat meanings.
- Responses appear as `[NPC] Edric tells you privately, "..."` in the existing
  plain-text transcript. Only the normal server snapshot updates room and inventory.
- NPC conversations are available to authenticated players when the server enables
  them; they do not require admin narration access or narration opt-in.

## Configuration

`AI_NPC_ENABLED=false` is the default. Set it to `true` in the ignored local `.env`
and recreate the backend after the required test gate. It is independent of
`AI_COMMAND_INTERPRETATION_ENABLED` and `AI_NARRATION_ENABLED`.

The configured provider is shared by interpretation, narration, and dialogue.
`AI_PROVIDER=fake` gives deterministic greetings, approved Inn/Town Square facts,
and a recollection fixture triggered by `remember`. The existing OpenAI adapter
supports NPC dialogue with the same explicit model, credentials, development-only
restriction, transport bounds, and no-retry policy. Tests use fake or mocked HTTP
providers; live response quality is not established by those tests.

One attempted reply consumes one request from the existing daily account allowance.
Invalid syntax, unknown or absent NPCs, disabled dialogue, and invalid authorization
do not consume allowance. Provider failures count. `talk` bypasses interpretation
and additional narration, so it cannot consume three requests for one exchange.

## Authority, knowledge, and privacy

The server checks the authenticated character's ownership and co-location before
calling the provider and again before storing and returning the reply. The provider
receives only Edric's authored name, personality, goals, approved knowledge, a
server-derived familiarity label, this player's latest completed exchange, and the
new message. NPC queries select explicit columns rather than loading the world.

Edric's knowledge is deliberately small: his work at the Inn, its lanterns and
wood fire, and the Town Square west of the Inn. His private backstory secret is
stored server-side and is never sent to the provider or browser. There is no secret
revelation policy in M4. No other player's memory, identity, inventory, hidden room,
full map, account identifier, credential, or unrelated chat is included.

The reply schema accepts only text, with a 600-character maximum and no extra
fields. Dialogue is never parsed as an action or used to award items, create quests,
move characters, or update trust. Prompt instructions restrict claims to approved
knowledge, but prose can still be inaccurate. The engine remains authoritative.
Player claims and prior dialogue are explicitly untrusted conversation, not facts.

With a real provider enabled, the current message and retained exchange are sent
externally. Player text may itself contain identifying information. The adapter
uses `store=false`; this does not promise zero provider retention. Dialogue and
provider error content are excluded from application logs.

## Persistent memory and concurrency

Migration `0009` adds `npcs` and `npc_memories`. Startup seeds Edric without
resetting existing state. Memory is keyed by NPC and character, with cascading
cleanup when either is deleted. Each row stores only the most recent successful
exchange and the count of completed interactions; a new successful exchange
replaces the previous one. The row persists across reconnect and server restart.
There is no automatic time-based expiry or history archive in this increment.

Familiarity progresses from stranger to returning visitor after one completed
exchange, and familiar visitor after three. This is recognition, not earned trust
or authorization. Rich summaries, promises, favors, conflicts, and quest memories
are deferred until corresponding authoritative gameplay exists.

Input is limited to 400 characters, output to 600, and serialized context to
4,096 UTF-8 bytes. If Unicode-heavy history exceeds the context budget, it is omitted
from that request; familiarity remains. Lower configured provider limits can still
reject a request safely.

No game lock or database transaction spans the provider call. Other players can
continue playing or talking. On completion, a short player-row lock serializes the
memory update against movement and other replies. An optimistic interaction count
rejects a stale concurrent reply instead of overwriting newer memory. Session
authorization and active connection are rechecked. Failures and stale replies do
not write memory. A player's WebSocket still processes commands sequentially.

## Verification

Verification on September 7, 2026; every command below exited 0:

- Full Docker backend unit/integration suite: 250 passed, 91% overall coverage.
  Two existing dependency deprecation warnings remain.
- After adding five more edge-case tests, the final NPC service suite passed all
  22 tests, including concurrent first replies, Unicode-heavy context, ownership,
  bounded memory/familiarity, and seed idempotence. No application code changed
  between the full suite and this supplemental run.
- Ruff passed on application and test code; mypy passed on 45 source files.
- Frontend lint, types, all 18 unit tests, and build passed.
- `scripts\e2e.bat`: all 9 browser workflows passed in 48.5 seconds, including
  Edric's private conversation, allowance updates, reload memory, and room checks.
- `scripts\validate-production.bat`: hardened configuration validation and both
  production application image builds passed. This did not deploy a public stack.
- Migration `0009` applied successfully to fresh isolated PostgreSQL databases.
  Test containers were removed after verification; no live AI requests were made.

The initial implementation verification did not include the full local deployment
script or load smoke test. The project owner subsequently confirmed local deployment
and working dialogue on September 8, 2026. That confirmation does not establish
unrecorded deployment-gate results or a formal live-provider quality evaluation.
