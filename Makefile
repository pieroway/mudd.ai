.PHONY: help dev down test e2e deploy clean logs build

help:
	@echo "MUD AI - Available commands:"
	@echo "  make dev          - Start development environment"
	@echo "  make down         - Stop all services"
	@echo "  make test         - Run unit tests"
	@echo "  make e2e          - Run Playwright E2E tests"
	@echo "  make deploy       - Full deployment pipeline (test + build + run)"
	@echo "  make build        - Build Docker images"
	@echo "  make logs         - Follow backend logs"
	@echo "  make clean        - Remove containers and volumes"

dev:
	@echo "🚀 Starting development environment..."
	docker compose up -d
	@echo "✅ Services started:"
	@echo "   Backend:  http://localhost:8000"
	@echo "   Frontend: http://localhost:5173"
	@echo "   Postgres: localhost:5432"

down:
	@echo "🛑 Stopping services..."
	docker compose down

build:
	@echo "🔨 Building Docker images..."
	docker compose build

test:
	@echo "🧪 Running unit tests..."
	@cmd /c scripts\test.bat

e2e:
	@echo "🎭 Running E2E tests..."
	./scripts/e2e.sh

deploy: test build dev
	@echo "✅ Deployment complete!"

clean:
	@echo "🧹 Cleaning up..."
	docker compose -f compose.test.yaml down -v 2>/dev/null || true
	docker system prune -f
	@echo "✅ Cleaned"

logs:
	docker compose logs -f backend

.DEFAULT_GOAL := help
