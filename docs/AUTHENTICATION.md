# Player authentication

Accounts own characters; WebSocket connections do not choose an identity by
username. Registration creates an account and a new character atomically.
Passwords are hashed with Argon2id (19 MiB, two iterations, one lane); hashing
runs off the event loop with at most four active hash operations per process.
Passwords must contain 8–128 characters, including a number (0-9) and a special character. Login errors do not distinguish an
unknown account from an incorrect password. Credentials never pass through AI.
Whitespace does not count as a special character. These rules apply when creating
an account, including operator adoption; existing passwords remain valid for login.
The hashing parameters follow the [OWASP password storage guidance](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html).

## Browser workflow

Use **Create a new account**, enter a unique username and passphrase, and submit.
Returning players use **Sign in**. Reloading the page restores a valid session
and the character's persisted location and inventory. **Sign out** revokes the
current session. Other separately authenticated browser sessions remain valid.
Only one connection can play a character at a time in the current single-process
server.

The browser holds an opaque random token in an HTTP-only, SameSite=Strict,
host-only cookie. Tokens never appear in URLs or localStorage. PostgreSQL stores
only SHA-256 digests of tokens, account ownership, and absolute expiry times.
The cookie is Secure outside development/test, requiring HTTPS. The default
session lifetime is 24 hours. Login rotates the current cookie and invalidates
its previous server session. Expired rows are cleaned up when sessions are created.

HTTP credential writes and logout require an exact trusted Origin. Native clients
must supply a configured Origin on authentication POSTs and retain the cookie
for WebSocket connections. Browser WebSocket origins remain checked. Both local
frontend/backend URLs must use the same host (for example, both `localhost`).
Production routes `/auth/*` through the same TLS entry point as `/ws`.

The server checks session validity at connection, before each command, again
before engine execution after AI interpretation or command queuing, and before
sending game output. Idle connections also check expiry every 30 seconds. An
already executing transaction may complete during logout;
revocation blocks subsequent commands and output. Idle revoked sockets close
within 30 seconds, and cannot receive new game output or issue commands meanwhile.

## Existing characters

Migration 0006 preserves all existing characters, inventory, and world state.
Their names are reserved, and public registration cannot claim them. Existing
characters initially have no account and therefore cannot sign in.

After verifying the person's ownership, the local operator can create an account
for that character through Docker:

```powershell
docker compose exec backend python -m app.account_admin "Alan"
```

This prompts for a new password twice without echoing it. Never put passwords in
command arguments. It refuses characters already linked to an account and leaves
their game state intact. There is no browser claim endpoint or default password.
Existing character passwords must be established by this explicit operator step;
the migration cannot prove who owned a previous unauthenticated username.

## Limits and remaining work

`AUTH_SESSION_SECONDS` controls lifetime (60–604800 seconds, default 86400).
`AUTH_ATTEMPT_LIMIT` and `AUTH_ATTEMPT_WINDOW_SECONDS` default to 20 authentication
attempts per source address per 60 seconds. Successful attempts also count.
These settings are exposed by the Compose environment. Request bodies are capped
at 2 KiB and invalid credential fields are not echoed in errors.

Runtime services reuse a bounded PostgreSQL connection pool (five retained
connections plus at most five overflow connections) so repeated authorization
checks do not open a new database connection each time. Connections are checked
before reuse and closed at application shutdown. Pytest disables pooling with
`DATABASE_POOL_ENABLED=false` because its fixtures and HTTP client use different
event loops; browser and load tests exercise the runtime pool.

Authentication throttling and active-character presence are process-local. Use
one backend process until distributed throttling/presence is implemented. Do not
trust arbitrary forwarded client-address headers at a public proxy. The load-test
stack deliberately raises the authentication limit for its shared source address.

This first increment has no email verification, MFA, password change, self-service
recovery, or administrator web interface. Account-targeted throttling, compromised
password screening, and a public-launch dynamic security review remain future
work. Real AI stays development-only pending shared usage-budget controls.

## Validation

Automated tests cover registration, duplicate/concurrent registration, password
verification, token rotation, cookie flags, expiry, logout, WebSocket identity,
preservation/operator adoption of legacy characters, and revocation before engine
execution. Gameplay tests authenticate through real HTTP routes. Playwright covers
registration, reload, wrong passwords, logout, and persistent character location.
All AI in automated tests is fake or uses mocked HTTP transport.

The full Docker deployment gate passed with exit code 0 on September 4, 2026:
168 backend tests, 14 frontend tests, six Playwright workflows, lint, type checks,
production configuration validation, image builds, and authenticated smoke load
testing. The load run used 10 concurrent clients for 30 seconds; command latency
was 276.2 ms at p95 (limit 1 second), with all 40 checks passing. Authoritative-state
invariants passed. A separate backend `pip-audit --local` exited 0 with no known
vulnerabilities; the unpublished application package was skipped by the auditor.

Migration to revision `0006` preserved all eight existing characters and five
items: ordered row checksums before and after migration were identical. Earlier
gate failures stopped deployment; connection pooling fixed the latency failure,
and fresh-response assertions with paced typing fixed the browser timing issue.
