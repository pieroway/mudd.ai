@echo off
setlocal

echo Building test images...
docker compose -f compose.test.yaml build backend_test frontend_test
if errorlevel 1 goto failure

echo Running backend unit and integration tests...
docker compose -f compose.test.yaml run --rm backend_test
if errorlevel 1 goto failure

echo Running backend lint...
docker compose -f compose.test.yaml run --rm backend_test ruff check app tests
if errorlevel 1 goto failure

echo Running backend type checking...
docker compose -f compose.test.yaml run --rm backend_test mypy app
if errorlevel 1 goto failure

echo Running frontend lint, type checking, unit tests, and build...
docker compose -f compose.test.yaml run --rm frontend_test
if errorlevel 1 goto failure

docker compose -f compose.test.yaml down
echo All required unit checks passed.
exit /b 0

:failure
set TEST_EXIT=%errorlevel%
docker compose -f compose.test.yaml down
echo Test gate failed. Deployment blocked.
exit /b %TEST_EXIT%
