#!/bin/bash
set -euo pipefail

if [ ! -f .env ]; then
  cp .env.example .env
fi

echo "Running required test gate..."
./scripts/test.sh

echo "Building application images..."
docker compose build

echo "Starting application stack and waiting for health checks..."
docker compose up -d --wait

echo "Running Playwright workflow..."
./scripts/e2e.sh

echo "Deployment gate passed."
echo "Frontend: http://localhost:5173"
echo "Backend:  http://localhost:8000"
