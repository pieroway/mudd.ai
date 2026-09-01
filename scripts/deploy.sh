#!/bin/bash
set -e

echo "🔍 Validating environment..."
if [ ! -f .env ]; then
  echo "⚠️  .env not found, copying from .env.example"
  cp .env.example .env
fi

echo "📦 Running test gate..."
./scripts/test.sh
if [ $? -ne 0 ]; then
  echo "❌ Test gate failed. Deployment stopped."
  exit 1
fi

echo "🐳 Building Docker images..."
docker compose build

echo "🚀 Starting application stack..."
docker compose up -d

echo "⏳ Waiting for health checks..."
sleep 5

echo "📊 Service status:"
docker compose ps

echo "✅ Deployment complete!"
echo ""
echo "   🌐 Frontend:  http://localhost:5173"
echo "   🔌 Backend:   http://localhost:8000"
echo "   📊 Postgres:  localhost:5432"
echo ""
echo "View logs: make logs"
exit 0
