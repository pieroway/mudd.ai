.PHONY: help dev down test audit e2e deploy clean logs build load-smoke load-test load-stress load-crowded

help:
	@echo "MUD AI - Available commands:"
	@echo "  make dev          - Start development environment"
	@echo "  make down         - Stop all services"
	@echo "  make test         - Run unit tests"
	@echo "  make audit        - Audit Python, frontend, and Playwright dependencies"
	@echo "  make e2e          - Run Playwright E2E tests"
	@echo "  make deploy       - Full gate (tests + build + E2E + load smoke)"
	@echo "  make load-smoke   - Run a 10-player local WebSocket load test"
	@echo "  make load-test    - Run a 100-player local WebSocket baseline"
	@echo "  make load-stress  - Run a 500-player local WebSocket stress test"
	@echo "  make load-crowded - Run a 100-player crowded-room fan-out test"
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

audit:
	@cmd /c scripts\audit.bat

e2e:
	@echo "🎭 Running E2E tests..."
	@cmd /c scripts\e2e.bat

deploy:
	@cmd /c scripts\deploy.bat

load-smoke:
	@cmd /c scripts\load-test.bat smoke

load-test:
	@cmd /c scripts\load-test.bat baseline

load-stress:
	@cmd /c scripts\load-test.bat stress

load-crowded:
	@cmd /c scripts\load-test.bat crowded

clean:
	@echo "🧹 Cleaning up..."
	docker compose -f compose.test.yaml down -v 2>/dev/null || true
	docker system prune -f
	@echo "✅ Cleaned"

logs:
	docker compose logs -f backend

.DEFAULT_GOAL := help
