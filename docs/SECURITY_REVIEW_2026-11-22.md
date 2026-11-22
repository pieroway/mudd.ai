# Mudd.ai Security Review November 22, 2026

The inspected configuration is appropriate for a trusted local environment once
the development ports are restricted. Public deployment should wait for the
critical TLS dependency update, the high-priority availability fixes, and a
passing dependency gate on the release images.

## Scope and evidence

The review covered commit `d52094d` on `master` and the in-progress narration
library. It included authentication, sessions, role checks, game and map
authorization, AI request and result handling, browser rendering, container and
proxy configuration, dependency advisories, release controls, and backup tooling.
The September review remains the historical baseline.
[September security review](SECURITY_REVIEW_2026-09-02.md)

Local requests without a session returned HTTP 401 from `/auth/me`,
`/auth/world-map`, and `/auth/maze-map`. The code uses Argon2 password hashing,
hashed revocable session tokens, exact browser origins, role checks at privileged
endpoints, and parameterized ORM queries. The browser renders transcript content
as text. The engine continues to decide and persist gameplay outcomes.
[Authentication service](../backend/app/services/auth.py) ·
[Authorization endpoints](../backend/app/api/auth.py) ·
[Maze map](../backend/app/api/maze_map.py) ·
[Transcript](../frontend/src/components/Transcript.tsx) ·
[Game service](../backend/app/services/game.py)

The review used source inspection, local endpoint checks, and dependency audits.
It did not include active intrusion testing, cloud or firewall inspection, or
verification of GitHub branch protection and past CI runs. Docker Scout required
a Docker account, so operating-system package advisories in the base images
remain unverified. A limited search of reachable Git history found no matches
for the checked API key and private-key formats. It did not replace a dedicated
secret scan or inspect the ignored local configuration.

## Prioritized actions

### P0 Update the Python TLS trust bundle

The installed backend production image contains `certifi 2026.7.22`, affected by
critical advisory `PYSEC-2026-4320`. The advisory concerns compromised
intermediate certificate authority keys. A party with the required network
position and compromised key could intercept connections that trust the bundle.
The OpenAI adapter uses HTTPX and sends an API credential over HTTPS.
[Certifi advisory](https://github.com/certifi/python-certifi/security/advisories/GHSA-6q48-6c7w-9gw2) ·
[PyPA advisory record](https://osv.dev/vulnerability/PYSEC-2026-4320) ·
[OpenAI adapter](../backend/app/ai/openai.py)

- Lock `certifi` to a patched version. Use `2026.10.19` or a newer verified
  release per the advisory. Rebuild backend images before using the paid
  provider on an untrusted network.
- Verify the installed version and rerun the audit on the rebuilt production
  image. Check the normal HTTPS provider connection in an authorized environment.

### P1 Restrict development ports and patch the frontend toolchain

The running development frontend and API publish ports 5173 and 8000 on all
IPv4 and IPv6 interfaces. Actual access from other machines also depends on the
host firewall. This exposes an HTTP development setup beyond the loopback
interface. The frontend audit flagged Vite 8.2.2 and its dependency tree.
The production frontend serves prebuilt files through a separate static server.
[Development Compose](../compose.yaml) ·
[Frontend Dockerfile](../frontend/Dockerfile) ·
[Vite file-serving advisory](https://github.com/advisories/GHSA-rq7h-c2jc-7f22) ·
[Vite middleware advisory](https://github.com/advisories/GHSA-9jrq-w75r-8gcw)

- Bind the published development ports to loopback by default. Use an explicit
  separate profile when testing from another device.
- Upgrade and lock Vite, Vitest, ESLint-related dependencies, and affected
  transitives. Verify the listener bindings, rerun the frontend audit, and run
  Playwright against the rebuilt stack.

### P1 Close gaps in release and runtime dependency auditing

The dependency workflow has pull request and scheduled triggers. Its direct
push trigger targets `main`, while the verified default branch is `master`.
The Windows deployment gate builds production images but does not invoke the
dependency audit. The build also installs `http-server` globally without a
version or lockfile. The installed static server tree contained a high-severity
finding for `follow-redirects 1.16.0` and a moderate finding for `qs 6.16.0`.
The server is configured
to serve files, and the review did not establish reachability of the affected
redirect behavior.
[Dependency workflow](../.github/workflows/dependency-audit.yml) ·
[Deployment gate](../scripts/deploy.bat) ·
[Frontend Dockerfile](../frontend/Dockerfile) ·
[Redirect advisory](https://github.com/advisories/GHSA-q3jh-wrc6-jgq8)

- Correct the branch trigger and require a passing audit for releases. Pin and
  lock the production static server and its dependencies, or replace it with
  a pinned and scanned static server.
- Patch the Python development dependencies `black` and `filelock`. Scan the
  release images and base OS packages. Verify the workflow triggers on a
  dependency-only change to `master` and records a result for each release image.

### P1 Make WebSocket admission limits recoverable and atomic

The connection-attempt table expires timestamps only when the same address
returns. It retains inactive address entries, so reaching the table limit can
deny new addresses until a process restart. The active-connection limit is
checked before session resolution and socket acceptance await, so concurrent
handshakes can pass the same capacity check. In the production-like profile,
the gateway and backend are separate containers. The backend supplies no
trusted-proxy override, and the installed Uvicorn defaults to trusting proxy
headers from loopback. Without additional deployment configuration, requests
behind the gateway can share a peer address for authentication and connection
rate limits.
[WebSocket admission](../backend/app/api/websocket.py#L58) ·
[Authentication limiter](../backend/app/api/auth.py#L27) ·
[Gateway configuration](../docker/Caddyfile) ·
[Production Compose](../compose.production.yaml)

- Expire inactive address keys and bound cleanup work. Reserve and release
  connection slots atomically across authentication, acceptance, and disconnect.
- Trust forwarded client addresses only from the designated gateway. Verify
  that inactive entries release capacity, simultaneous handshakes respect
  the cap, and separate clients behind the gateway get independent rate limits.

### P1 Separate the runtime database role from migration ownership

The production example uses the same identity for the PostgreSQL bootstrap user
and the backend connection. The PostgreSQL image creates its bootstrap user as
a superuser. The backend also runs migrations at startup with its application
credentials. Following the example makes a backend credential compromise
more damaging and weakens the protection offered by database constraints and
triggers.
[Production environment example](../.env.production.example) ·
[Production Compose](../compose.production.yaml) ·
[God account protection migration](../backend/alembic/versions/0021_account_roles.py)

- Run migrations using a separate owner or migration role. Use a non-superuser
  app role with only the schema access and data privileges needed at runtime.
- Confirm the runtime role can play the game and write ordinary state. Verify
  it lacks privilege to administer roles, alter the schema, or disable triggers.

### P2 Harden shared narration before exposing paid AI publicly

The new library stores prose validated for shape and length. The browser can
display that prose in place of the deterministic outcome text. A model can
produce misleading prose even when the actual game state is correct. Shared
storage increases the number of players who can see a bad flourish. Concurrent
misses are coalesced within one process, while separate processes can each pay
for the same missing result. Per-account budgets and the provider's per-process
limits are in place. The library has no expiry or operator purge mechanism.
[Narration service](../backend/app/services/narration.py) ·
[Narration contract](../backend/app/ai/narration.py) ·
[Terminal display](../frontend/src/components/Terminal.tsx#L124) ·
[AI budget accounting](../backend/app/services/ai_usage.py)

- Keep the deterministic result visible and render AI prose as supplemental
  text. Add an operator purge mechanism and a retention policy for saved prose.
- Before enabling paid narration on a public server, enforce a durable aggregate
  spend ceiling and coordinate cache misses across workers. Verify that cached
  hits remain free and that restarts or simultaneous misses respect the ceiling.

### P2 Harden browser policy, sensitive logs, and recovery

The gateway sets HSTS, MIME and frame protections, and a referrer policy.
The reviewed configuration has no Content Security Policy and uses an internal
TLS CA. WebSocket error handlers log full exceptions, and the database engine
does not suppress SQL parameters. Backup tooling produces database dumps and
checksums for integrity. The review did not verify host disk encryption, off-host
backup access, or recent restore results.
[Gateway configuration](../docker/Caddyfile) ·
[Database configuration](../backend/app/db/__init__.py) ·
[WebSocket logging](../backend/app/api/websocket.py) ·
[Backup and restore tooling](../scripts/database.ps1)

- Validate a restrictive CSP in staging, then enforce it. Configure externally
  trusted TLS before public deployment and verify the browser accepts HTTPS
  and secure WebSockets without a manually installed certificate.
- Suppress SQL parameter values in exception reporting and verify that failures
  can be diagnosed with metadata alone. Protect backups with restricted access
  and encryption, and record a successful isolated restore drill.

## Dependency audit results

| Scope | Result |
| --- | --- |
| Python development and test image | 20 reported entries across `black`, `certifi`, and `filelock`. The tool listed the same `certifi` advisory twice. |
| Installed production Python packages | `certifi 2026.7.22` flagged for `PYSEC-2026-4320`, reported twice. |
| Frontend lockfile | 11 findings, including three high-severity entries. |
| Playwright lockfile | Zero reported findings. |
| Installed production static server | Two findings across 48 installed packages, one high and one moderate. |
| Base operating-system packages | Scan did not complete because Docker Scout required sign-in. |

These results reflect the advisory databases and image contents at review time.
Audit clean development and production builds again after updating the
dependencies.
