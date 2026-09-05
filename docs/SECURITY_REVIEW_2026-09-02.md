# Security Review — September 2, 2026

## Purpose and Scope

This document preserves the security baseline taken before Milestone Two. The
review covered application source, WebSocket identity and authorization, browser
rendering, database access, Docker configuration, secrets handling, input limits,
and current Python and Node dependency advisories.

This was a focused source and dependency review, not a penetration test. Findings
must be rechecked after remediation and before any public deployment.

## Deployment Assessment

The application is suitable for trusted local development. It is not ready to be
exposed to the public internet or an untrusted network.

## Findings

### SEC-001 — Username impersonation and missing authentication

- **Severity:** Critical for public deployment
- **Status:** Resolved September 4, 2026
- **Evidence:** A WebSocket query-string username is treated as the persistent
  player identity. Duplicate-name protection applies only while that player is
  connected.
- **Risk:** Anyone can reconnect as an offline player and access that player's
  persistent location and inventory.
- **Remediation:** Introduce authenticated accounts or signed development
  sessions. Separate account identity, character identity, and connection state.
- **Resolution:** Password-backed accounts now own characters. WebSockets resolve
  identity from revocable server-side sessions and ignore query-string usernames.
  Registration reserves legacy characters for explicit operator adoption. Tests
  cover impersonation, expiry, logout, and revocation before engine execution.
  See [authentication details and remaining public-launch work](AUTHENTICATION.md).

### SEC-002 — Unrestricted browser and WebSocket origins

- **Severity:** High
- **Status:** Resolved September 3, 2026
- **Evidence:** HTTP CORS allows `*` while credentials are enabled. The WebSocket
  endpoint performs no `Origin` validation and accepts the connection before
  player validation.
- **Risk:** An untrusted website can attempt cross-origin connections to the game.
- **Remediation:** Configure explicit trusted origins and reject an unapproved
  WebSocket origin before calling `accept()`.
- **Resolution:** HTTP CORS and browser WebSocket connections now share an exact,
  configurable `TRUSTED_ORIGINS` allowlist. Untrusted browser origins are rejected
  before WebSocket acceptance. Clients without an Origin header remain supported
  because Origin is a browser security boundary, not client authentication.

### SEC-003 — Development data services exposed with known credentials

- **Severity:** High on an untrusted local network
- **Status:** Resolved September 3, 2026
- **Evidence:** Development Compose publishes PostgreSQL on port 5432 using the
  documented `muduser`/`mudpass` credentials and publishes unauthenticated Redis
  on port 6379.
- **Risk:** Host-network users may reach authoritative or ephemeral game data,
  depending on host firewall rules.
- **Remediation:** Bind development ports to `127.0.0.1`, avoid publishing Redis
  unless required, and keep production credentials in managed secrets.
- **Resolution:** Development PostgreSQL now publishes only to
  `127.0.0.1:5432`. Redis no longer publishes a host port and remains reachable
  only by services on the private Compose network. Test, E2E, and load stacks
  already keep both data services internal. Public deployments must still replace
  the documented development credentials with managed secrets.

### SEC-004 — Known dependency vulnerabilities

- **Severity:** High
- **Status:** Resolved September 2, 2026
- **Evidence:** `pip-audit` reported 20 advisories across FastAPI 0.109.0,
  Starlette 0.35.1, python-multipart 0.0.6, and python-dotenv 1.0.0. Several relate
  to denial of service or malformed form processing. The application currently
  has no form or upload route, which reduces immediate exploitability.
- **Evidence:** The production-only Node audit reported zero vulnerabilities. The
  full frontend audit reported 10 development dependency findings, including old
  Vite, Vitest, TypeScript ESLint, esbuild, and minimatch versions. The E2E audit
  reported zero findings.
- **Remediation:** Upgrade compatible packages with tests. Remove
  `python-multipart` until a form/upload feature requires it. Upgrade the frontend
  toolchain and keep development servers off untrusted networks.
- **Resolution:** Upgraded FastAPI to 0.141.1, Pydantic to 2.13.5,
  pydantic-settings to 2.15.0, and python-dotenv to 1.2.3; removed the unused
  python-multipart dependency; upgraded Vite, Vitest, the Vite React plugin, and
  TypeScript ESLint; pinned all direct Node dependencies exactly. Follow-up
  `pip-audit` and full `npm audit` scans reported no known vulnerabilities. The
  full deployment gate also passed.

### SEC-005 — Missing connection, traffic, and input limits

- **Severity:** High
- **Status:** Resolved September 3, 2026
- **Evidence:** No explicit limits exist for WebSocket message size, command rate,
  connection attempts, chat length, reconnect attempts, or per-client outbound
  queues.
- **Risk:** A client can exhaust CPU, memory, database capacity, or the global
  command lock.
- **Remediation:** Add bounded command and chat lengths, connection and per-player
  rate limits, server/proxy WebSocket size limits, and bounded outgoing queues.
- **Resolution:** Configurable application and Uvicorn message-size limits now
  reject oversized UTF-8 commands before engine execution. Each connection has a
  sliding-window command limit; connection attempts are limited per source address;
  active WebSockets are capped per backend process; and every outbound send has a
  timeout. The service sends directly rather than maintaining unbounded application
  queues. Load-test Compose explicitly raises connection limits for its 500-client
  capacity scenario.

### SEC-006 — Raw commands may enter debug logs

- **Severity:** Medium
- **Status:** Resolved September 3, 2026
- **Evidence:** The WebSocket handler logs the complete received command at debug
  level.
- **Risk:** Private `tell` messages and future AI prompts may be retained in logs.
- **Remediation:** Log action metadata, identifiers, and sizes rather than raw
  private content. Define retention and redaction rules.
- **Resolution:** WebSocket command logs now contain only the server-generated
  session identifier, parsed action, UTF-8 byte count, success state, and elapsed
  time. Raw command, chat, target, username, and AI-prompt content are excluded.
  Automated log-capture tests cover both ordinary and private-message commands.
  Production log retention remains an operator responsibility and should be kept
  to the shortest period needed for reliability and incident investigation.

### SEC-007 — Development containers are not production hardened

- **Severity:** Medium
- **Status:** Resolved September 3, 2026
- **Evidence:** The development backend uses reload mode and bind-mounted source.
  The frontend Compose service runs the builder stage, exposes Vite on all
  interfaces, and does not inherit the final image's non-root user.
- **Risk:** These local conveniences increase impact if the development stack is
  reachable from an untrusted network.
- **Remediation:** Keep the development stack local. Define a separate hardened
  production-like profile with no reload or source mounts, non-root users,
  constrained capabilities, and TLS termination.
- **Resolution:** `compose.production.yaml` provides a separate TLS-terminated
  stack with no application or data-service ports exposed behind the gateway.
  Its application containers run as non-root with read-only root filesystems,
  all capabilities dropped, no-new-privileges enabled, and no development bind
  mounts or reload processes. Production database credentials and the public
  origin are required inputs. The deployment gate validates and builds the
  production-like application images before continuing.

### SEC-008 — Compiled Python artifacts are tracked

- **Severity:** Low
- **Status:** Resolved September 4, 2026
- **Evidence:** Tracked `__pycache__` directories and `.pyc` files remain in the
  repository even though new instances are ignored.
- **Risk:** Stale artifacts add repository noise and can obscure what source is
  actually executed.
- **Remediation:** Remove tracked compiled files in a dedicated cleanup change.
- **Resolution:** Removed the tracked Python bytecode and broadened `.gitignore`
  rules to exclude Python cache directories and compiled bytecode throughout the
  repository.

## Positive Controls Observed

- SQLAlchemy query construction showed no obvious string-built SQL injection.
- React renders transcript content as text; no `dangerouslySetInnerHTML` was found.
- Environment files are ignored and no committed live API key was detected.
- WebSocket session identifiers are generated by the server.
- Authoritative game mutations remain behind engine and transactional checks.
- Runtime Dockerfiles define non-root users, subject to the development exception
  described in SEC-007.

## Remediation Order

- [x] Upgrade or remove vulnerable dependencies (SEC-004).
- [x] Restrict HTTP and WebSocket origins (SEC-002).
- [x] Add input, connection, and rate limits (SEC-005).
- [x] Remove raw command content from logs (SEC-006).
- [x] Restrict development database and Redis ports (SEC-003).
- [x] Design and implement real authentication before public access (SEC-001).
- [x] Add automated dependency auditing to CI/deployment checks. `make audit`
  scans the pinned backend, frontend, and Playwright environments. GitHub
  Actions runs it for dependency changes, weekly, and on demand. All Python
  advisories and high/critical Node advisories fail the workflow; audit-service
  failures fail closed. The live lookup is intentionally separate from the
  deployment script so an advisory-service outage cannot break deployments.
- [x] Add a hardened production-like Compose profile (SEC-007).
- [x] Remove tracked compiled Python artifacts (SEC-008).
- [ ] Repeat this review and perform dynamic security testing before public launch.

## Milestone Two Boundary

M2 must not send user input to a real AI provider until prompt data handling,
timeouts, output schema validation, logging/redaction, and secret management are
defined. Automated tests must continue to use `FakeAIProvider` without network
calls or real credentials.

The development-only OpenAI adapter now defines these boundaries in README:
stateless minimal prompts, `store=false`, a total deadline, strict local schema
validation, generic errors, a redacted settings key, and bounded request/output
limits without retries. Adapter tests use an in-memory mock HTTP transport with
dummy credentials; gameplay tests continue to use FakeAIProvider. Production
activation is rejected. Persistent/shared cost accounting and authenticated
per-player quotas remain deferred; process-local limits reset on restart.
