#!/bin/bash
set -euo pipefail

echo "Building and starting the application stack..."
docker compose up -d --build --wait

echo "Building the Playwright test image..."
docker build -t muddai-e2e ./e2e

echo "Running browser tests..."
docker run --rm \
  --add-host=host.docker.internal:host-gateway \
  -e E2E_BASE_URL=http://host.docker.internal:5173 \
  muddai-e2e

echo "Playwright tests passed."
