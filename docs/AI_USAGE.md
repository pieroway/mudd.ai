# AI units and admin credit grants

Each authenticated account has a persistent daily allowance for natural-language
command interpretation, optional [narration](../MILESTONE_THREE_PLAN.md),
[NPC conversations](../MILESTONE_FOUR_PLAN.md), and admin-requested
[room generation](WORLD_GENERATION.md). Room proposal generation consumes one
dispatched attempt; preview, list, approval, rejection, and direct room-description
edits are free. Relative movement uses the classic engine without interpretation;
optional enabled narration can still consume a unit for its movement outcome.
`AI_DAILY_REQUEST_LIMIT` defaults to 50 units; one unit permits one attempted AI
request. Set it in `.env`
and recreate the backend to change it. Zero disables AI attempts while classic
commands continue to work. The supported range is 0–10000.

The terminal displays daily units separately from persistent bonus credits, plus
the total available when a bonus balance exists. Daily units reset at 00:00 UTC;
bonus credits do not expire. An idle display updates on the next command or
reconnect; a connected recipient also receives an immediate update after a grant.
This is a request allowance, not dollar credit
or a token balance. The provider may reject requests earlier because its existing
process-wide safety limit and concurrency limits still apply.

Before an AI attempt, PostgreSQL locks the account and spends an available daily
unit first. Once daily units are exhausted, it decrements one bonus credit instead.
The daily attempt counter includes both types of spending. Counter and bonus
updates commit together before the provider runs. Concurrent requests cannot
double-spend credits or exceed the available allowance, and restarting
the backend or signing in again does not reset usage. Database UTC time determines
the day. Reducing the configured limit never removes recorded usage.

Every reserved attempt counts, including timeouts, invalid interpretations and
upstream failures: their actual billing may be unknown. No automatic refund or
retry is attempted. Classic command execution does not consume allowance, but
optional narration after it consumes one request. A natural-language action can
use two requests (interpretation and narration). Disabled AI features consume none.
`talk <npc> <message>` uses one request for a reply, bypassing interpretation and
additional narration. It requires the player and NPC to be in the same room.
Narration defaults off per account. Only admins can opt in using `/ai narration on`;
`/ai narration off` disables it again. These commands consume no allowance.
Narration exhaustion or failure leaves the completed engine action intact.
A database reservation failure prevents the provider call.
Fake AI uses the same budget path in browser tests.

## Admin grants

Admins can grant credits to any existing account, including their own and accounts
that are offline. Use the account's username; lookup is case-insensitive. Names
containing spaces or apostrophes should be enclosed in double quotes.

```text
/ai credits add Alan
/ai credits add Alan 100
/ai credits add "Mary Jane" 75
```

Omitting the amount grants 50 units. Each grant must be a whole number from 1 to
10,000; the accumulated bonus balance cannot exceed 1,000,000. Granting is free
and does not call an AI provider. It is available even if AI features are disabled
or the admin's own allowance is exhausted. Help lists the command only for admins.
There is no deduction command or public credit endpoint in this increment.

The server rechecks the admin role under database locks and checks the active
session before committing a grant. It locks the admin and recipient in a stable
order, including self-grants, so simultaneous grants remain additive. Ordinary
users, revoked admins, expired sessions, nonexistent recipients, invalid amounts,
and grants exceeding the balance cap cannot change balances.

Migration `0010` gives existing and new accounts a zero bonus balance without
resetting daily usage. The grant record stores administrator, recipient, units,
and database timestamp in the same transaction as the balance increase. Grant
records remain until the recipient is deleted; deleting the granting admin clears
that reference. No dialogue or credentials are stored in grant records.

Setting the daily limit to zero still disables all AI spending, including bonus
credits, while preserving the bonus balance. Credits do not override feature
flags, development-only provider restrictions, or provider capacity/spending
limits. Existing explicit `.env` limits continue to override the new default.

Revision `0007` added `ai_daily_usage`, keyed by account and UTC day, without
changing existing characters or inventory. Rows retain only the attempt count;
no prompts, responses, API keys, token counts, or estimated charges are stored.
Usage belongs to the authenticated account; a WebSocket query cannot select a
different account's allowance. Historical daily rows currently remain until the
account is deleted; retention and operator reporting are future work.

This does not replace provider billing limits or make public registration safe
against account farming. A persistent global spending cap and account issuance
controls are still needed before public live-AI access. The existing restriction
of real AI to development remains in place.

## Credit grant verification

Implemented and verified in isolated environments on September 7, 2026:

- Backend unit/integration suite: 272 passed, 92% coverage, exit 0. This includes
  permission denial, self/offline grants, audit records, validation limits,
  concurrent grants and spending, daily reset, and reconnect persistence.
- Ruff and mypy passed (46 source files); frontend lint, types, all 19 unit tests,
  and build passed. All commands exited 0.
- `scripts\e2e.bat`: all 10 workflows passed, including immediate recipient
  balance updates, persisted bonus credits, regular-user denial, and self-grants.
- `scripts\validate-production.bat`: configuration validation and production
  image builds passed, exit 0. Migration `0010` applied in isolated PostgreSQL.

Two existing backend dependency deprecation warnings remain. No real AI requests
were made. This increment has not been deployed to the local development stack;
run `scripts\deploy.bat` before deployment. These checks do not claim a full
deployment-gate or load-smoke pass.
