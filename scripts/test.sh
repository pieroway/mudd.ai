#!/bin/bash
set -e

echo "🔨 Building test containers..."
docker compose -f compose.test.yaml build

echo "🧪 Running backend unit tests..."
docker compose -f compose.test.yaml run --rm backend_test
BACKEND_EXIT=$?

# Stop test services
docker compose -f compose.test.yaml down

# STOP if unit tests fail
if [ $BACKEND_EXIT -ne 0 ]; then
  echo "❌ Unit tests FAILED. Deployment blocked."
  exit 1
fi

echo "✅ All unit tests passed!"
exit 0
