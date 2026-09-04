#!/bin/bash
set -uo pipefail

cleanup() {
  docker compose -f compose.test.yaml down
}
trap cleanup EXIT

echo "Building pinned dependency-audit images..."
docker compose -f compose.test.yaml build backend_test frontend_test || exit 2
docker build -t muddai-e2e ./e2e || exit 2

echo "Auditing Python dependencies (all advisories block)..."
docker compose -f compose.test.yaml run --rm --no-deps backend_test pip-audit --local
backend_exit=$?

echo "Auditing frontend dependencies (high and critical advisories block)..."
docker compose -f compose.test.yaml run --rm --no-deps frontend_test npm audit --audit-level=high --fetch-retries=2 --fetch-timeout=60000
frontend_exit=$?
if [ "$frontend_exit" -ne 0 ]; then
  echo "Frontend audit failed; retrying once in case the advisory service was unavailable..."
  docker compose -f compose.test.yaml run --rm --no-deps frontend_test npm audit --audit-level=high --fetch-retries=2 --fetch-timeout=60000
  frontend_exit=$?
fi

echo "Auditing Playwright dependencies (high and critical advisories block)..."
docker run --rm muddai-e2e npm audit --audit-level=high --fetch-retries=2 --fetch-timeout=60000
e2e_exit=$?
if [ "$e2e_exit" -ne 0 ]; then
  echo "Playwright audit failed; retrying once in case the advisory service was unavailable..."
  docker run --rm muddai-e2e npm audit --audit-level=high --fetch-retries=2 --fetch-timeout=60000
  e2e_exit=$?
fi

if [ "$backend_exit" -ne 0 ] || [ "$frontend_exit" -ne 0 ] || [ "$e2e_exit" -ne 0 ]; then
  echo "Dependency audit failed. Review each tool's output to distinguish advisories from registry/service errors."
  exit 1
fi

echo "Dependency audit passed."
