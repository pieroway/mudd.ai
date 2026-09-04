@echo off
setlocal

echo Validating hardened production-like Compose configuration...
docker compose -p muddai-prod-validation --env-file .env.production.example -f compose.production.yaml config --quiet
if errorlevel 1 goto failure

echo Building production application images...
docker compose -p muddai-prod-validation --env-file .env.production.example -f compose.production.yaml build backend frontend
if errorlevel 1 goto failure

echo Production-like configuration validation passed.
exit /b 0

:failure
echo Production-like configuration validation failed.
exit /b 1
