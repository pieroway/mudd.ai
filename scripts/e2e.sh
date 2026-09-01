#!/bin/bash
set -e

echo "🎭 Running end-to-end tests with Playwright..."

# Install dependencies if needed
if [ ! -d "e2e/node_modules" ]; then
  echo "📦 Installing e2e dependencies..."
  cd e2e
  npm install
  cd ..
fi

# Run Playwright tests
cd e2e
npx playwright test

if [ $? -ne 0 ]; then
  echo "❌ E2E tests FAILED"
  exit 1
fi

echo "✅ E2E tests passed!"
exit 0
