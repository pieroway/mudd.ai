#!/bin/bash
set -euo pipefail

if [ ! -f .env ]; then
  cp .env.example .env
fi

echo "Running required test gate..."
./scripts/test.sh

./scripts/validate-production.sh

echo "Building application images..."
docker compose build

echo "Running Playwright workflow..."
./scripts/e2e.sh

echo "Running smoke load test and authoritative-state checks..."
./scripts/load-test.sh smoke

echo "Starting application stack and waiting for health checks..."
docker compose up -d --wait

echo "Deployment gate passed."
echo "Frontend: http://localhost:5173"
echo "Backend:  http://localhost:8000"
