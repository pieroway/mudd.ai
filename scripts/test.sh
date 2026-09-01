#!/bin/bash
set -euo pipefail

cleanup() {
  docker compose -f compose.test.yaml down
}
trap cleanup EXIT

echo "Building test images..."
docker compose -f compose.test.yaml build backend_test frontend_test

echo "Running backend unit and integration tests..."
docker compose -f compose.test.yaml run --rm backend_test

echo "Running backend lint..."
docker compose -f compose.test.yaml run --rm backend_test ruff check app tests

echo "Running backend type checking..."
docker compose -f compose.test.yaml run --rm backend_test mypy app

echo "Running frontend lint, type checking, unit tests, and build..."
docker compose -f compose.test.yaml run --rm frontend_test

echo "All required unit checks passed."
