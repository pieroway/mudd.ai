# Daily AI request allowance

Each authenticated account has a persistent daily allowance for natural-language
command interpretation. `AI_DAILY_REQUEST_LIMIT` defaults to 20; set it in `.env`
and recreate the backend to change it. Zero disables AI attempts while classic
commands continue to work. The supported range is 0–10000.

The terminal displays remaining requests for the current UTC day when connecting
and after each command. The allowance resets at 00:00 UTC; an idle display updates
on the next command or reconnect. This is a request allowance, not dollar credit
or a token balance. The provider may reject requests earlier because its existing
process-wide safety limit and concurrency limits still apply.

Before an AI attempt, PostgreSQL atomically inserts or increments the account's
daily counter only if it is below the limit. The transaction commits before the
provider runs. Concurrent requests cannot exceed the allowance, and restarting
the backend or signing in again does not reset usage. Database UTC time determines
the day. Reducing the configured limit never removes recorded usage.

Every reserved attempt counts, including timeouts, invalid interpretations and
upstream failures: their actual billing may be unknown. No automatic refund or
retry is attempted. Classic commands and commands while AI is disabled do not
consume allowance. A database reservation failure prevents the provider call.
Fake AI uses the same budget path in browser tests.

Revision `0007` adds `ai_daily_usage`, keyed by account and UTC day, without
changing existing characters or inventory. Rows retain only the attempt count;
no prompts, responses, API keys, token counts, or estimated charges are stored.
Usage belongs to the authenticated account; a WebSocket query cannot select a
different account's allowance. Historical daily rows currently remain until the
account is deleted; retention and operator reporting are future work.

This does not replace provider billing limits or make public registration safe
against account farming. A persistent global spending cap and account issuance
controls are still needed before public live-AI access. The existing restriction
of real AI to development remains in place.
