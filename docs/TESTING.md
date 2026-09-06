# Testing Strategy

Use pytest for backend unit/integration tests, a suitable frontend unit framework, and Playwright for browser E2E.

## Test pyramid

Many unit tests; some component/API/WebSocket/database integration tests; fewer Playwright E2E tests.

Playwright does not replace unit testing.

## Compose isolation

`compose.test.yaml` declares the project name `muddai-test`, so its network and
cleanup are separate from the development project. Do not override it with the
development project name through `-p` or `COMPOSE_PROJECT_NAME`.

Previously both stacks used the same default project name. Test cleanup could
remove the development network while stopped development containers still
referenced its old ID, causing `network ... not found` at deployment startup.
For that stale-container condition, after the required gate has passed, recreate
the affected containers with `docker compose up -d --force-recreate --wait postgres redis`,
then finish startup with `docker compose up -d --wait`. Existing database volumes
are retained; no volume deletion is required.

## Deployment gate

At minimum, unit tests must pass before Docker Desktop deployment.

Suggested order:
1. lint
2. type checks
3. backend unit tests
4. frontend unit tests
5. build
6. integration tests
7. Playwright
8. deploy

## Multiplayer tests

Cover two simultaneous users, room speech, arrival/departure, shared dropped items, item transfer, concurrent pickup, merchant stock races, and direct trade atomicity.

Use separate Playwright browser contexts for separate users.
