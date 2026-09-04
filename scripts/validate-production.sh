#!/bin/bash
set -euo pipefail

echo "Validating hardened production-like Compose configuration..."
docker compose -p muddai-prod-validation --env-file .env.production.example -f compose.production.yaml config --quiet

echo "Building production application images..."
docker compose -p muddai-prod-validation --env-file .env.production.example -f compose.production.yaml build backend frontend

echo "Production-like configuration validation passed."
