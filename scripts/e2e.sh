#!/bin/bash
set -euo pipefail

cleanup() {
  docker compose -p muddai-e2e -f compose.e2e.yaml down -v
}
trap cleanup EXIT

echo "Building and starting the isolated E2E stack..."
docker compose -p muddai-e2e -f compose.e2e.yaml up -d --build --wait

echo "Building the Playwright test image..."
docker build -t muddai-e2e ./e2e

echo "Running browser tests..."
mkdir -p e2e/test-results
docker run --rm \
  --add-host=host.docker.internal:host-gateway \
  -e E2E_BASE_URL=http://host.docker.internal:15173 \
  -v "$(pwd)/e2e/test-results:/tests/test-results" \
  muddai-e2e

echo "Playwright tests passed."
