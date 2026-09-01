# Testing Strategy

Use pytest for backend unit/integration tests, a suitable frontend unit framework, and Playwright for browser E2E.

## Test pyramid

Many unit tests; some component/API/WebSocket/database integration tests; fewer Playwright E2E tests.

Playwright does not replace unit testing.

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
